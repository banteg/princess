"""CLI tool for labeling TTS generated from choices."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Container, Horizontal
from textual.binding import Binding
from textual.reactive import reactive

from princess.tts.database import TTSDatabase


class AudioPlayer:
    """Simple audio player for FLAC files."""

    def __init__(self):
        """Initialize the audio player."""
        self.current_process = None

    def play(self, file_path: str) -> None:
        """Play an audio file.

        Args:
            file_path: Path to the audio file
        """
        import subprocess
        import platform
        import os

        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        # Stop any currently playing audio
        self.stop()

        # Choose the appropriate command based on platform
        system = platform.system()
        if system == "Darwin":  # macOS
            cmd = ["afplay", file_path]
        elif system == "Linux":
            cmd = ["aplay", file_path]
        elif system == "Windows":
            cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{file_path}').PlaySync();"]
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

        # Start the process
        print(f"Playing audio file: {file_path}")
        try:
            self.current_process = subprocess.Popen(cmd)
        except Exception as e:
            print(f"Error playing audio: {str(e)}")
            raise

    def stop(self) -> None:
        """Stop the currently playing audio."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                print("Stopped audio playback")
            except Exception as e:
                print(f"Error stopping audio: {str(e)}")
            finally:
                self.current_process = None


class TTSLabelApp(App):
    """Textual TUI app for labeling TTS files."""

    # Load custom CSS
    CSS_PATH = Path(__file__).parent / "tts_label.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "play", "Play audio"),
        Binding("s", "stop", "Stop audio"),
        Binding("1", "play_context_1", "Play with 1 line context"),
        Binding("2", "play_context_2", "Play with 2 lines context"),
        Binding("3", "play_context_3", "Play with 3 lines context"),
        Binding("a", "approve", "Approve"),
        Binding("r", "reject", "Reject"),
        Binding("n", "next", "Next file"),
    ]

    current_file = reactive(None)

    def __init__(self, db_path: str, tts_dir: str, game_path: Optional[str] = None):
        """Initialize the app.

        Args:
            db_path: Path to the SQLite database
            tts_dir: Directory containing TTS files
            game_path: Path to the game directory
        """
        super().__init__()
        self.db = TTSDatabase(db_path)
        self.tts_dir = tts_dir
        self.game_path = game_path or os.environ.get("GAME_PATH", "")
        self.audio_player = AudioPlayer()

    def on_mount(self) -> None:
        """Load the next file when the app starts."""
        self.load_next_file()
        # update_stats is already called by load_next_file

    def compose(self) -> ComposeResult:
        """Create the UI components."""
        yield Header()

        with Container(id="main"):
            # Stats display
            yield Static("", id="stats-display")

            # Combined content section
            with Container(id="content-section"):
                yield Static("", id="content-display")

            # Controls section
            with Horizontal(id="controls-section"):
                yield Button("Play (p)", id="play-btn", variant="primary")
                yield Button("Stop (s)", id="stop-btn", variant="default")
                yield Button("Approve (a)", id="approve-btn", variant="success")
                yield Button("Reject (r)", id="reject-btn", variant="error")
                yield Button("Next (n)", id="next-btn", variant="default")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "play-btn":
            self.action_play()
        elif button_id == "stop-btn":
            self.action_stop()
        elif button_id == "approve-btn":
            self.action_approve()
        elif button_id == "reject-btn":
            self.action_reject()
        elif button_id == "next-btn":
            self.action_next()

    def watch_current_file(self, file: Optional[Dict[str, Any]]) -> None:
        """Update the UI when the current file changes."""
        if file is None:
            self.query_one("#content-display").update("No more files to label")
            return

        # Clear existing content
        content_display = self.query_one("#content-display")
        content_display.remove_children()

        # Get file paths
        file_path = file["file_path"]
        if isinstance(file_path, str) and Path(file_path).name:
            file_name = Path(file_path).name
        else:
            file_name = str(file_path)

        # Add file info
        from textual.widgets import Static

        file_info = Static(f"File: {file_name}\nSource: {file['filename']}:{file['lineno']}")

        # Add audio file path info
        tts_path = os.path.join(self.tts_dir, f"{Path(file_path).stem}.flac")
        audio_path_info = Static(f"Audio path: {tts_path}")

        content_display.mount(file_info, audio_path_info)

        # Add context before
        if file["context_before"]:
            context_before = Static("Context Before:")
            content_display.mount(context_before)

            for ctx in file["context_before"]:
                # For context lines, add file paths for voice files
                ctx_text = f"{ctx['character']}: {ctx['text']}"

                if "lineno" in ctx:
                    # Try to find the voice file path
                    voice_path = self._find_game_voice_file(file["filename"], ctx.get("lineno", 0))
                    if voice_path:
                        ctx_text += f"\nVoice: {voice_path}"

                ctx_static = Static(ctx_text)
                content_display.mount(ctx_static)

            content_display.mount(Static(""))

        # Add the choice in the middle with clean TTS text
        from textual.widgets import Static

        current_choice = Static(
            f"Current Choice: {file['clean_tts_text']}", classes="choice-highlight"
        )
        content_display.mount(current_choice)
        content_display.mount(Static(""))

        # Add context after
        if file["context_after"]:
            context_after = Static("Context After:")
            content_display.mount(context_after)

            for ctx in file["context_after"]:
                # For context lines, add file paths for voice files
                ctx_text = f"{ctx['character']}: {ctx['text']}"

                if "lineno" in ctx:
                    # Try to find the voice file path
                    voice_path = self._find_game_voice_file(file["filename"], ctx.get("lineno", 0))
                    if voice_path:
                        ctx_text += f"\nVoice: {voice_path}"

                ctx_static = Static(ctx_text)
                content_display.mount(ctx_static)

            content_display.mount(Static(""))

        # Add original choice text
        content_display.mount(Static(f"Original: {file['choice_text']}"))

        # Update the window title with the current choice hash
        self.title = f"TTS Labeling - {Path(file_path).stem}"

    def update_stats(self) -> None:
        """Update the statistics display."""
        from textual.widgets import Static, ProgressBar
        from textual.containers import Horizontal

        stats = self.db.get_stats()

        if stats["total_files"] > 0:
            progress = (stats["approved"] + stats["rejected"]) / stats["total_files"] * 100
        else:
            progress = 0

        # Clear existing stats content
        stats_widget = self.query_one("#stats-display")
        stats_widget.remove_children()

        # Create a nice progress bar with colored stats
        progress_bar = ProgressBar(total=100, show_percentage=True)
        progress_bar.update(progress=progress)
        stats_widget.mount(progress_bar)

        # Create horizontal containers for stats rows
        row1 = Horizontal(classes="stats-row")
        row2 = Horizontal(classes="stats-row")
        stats_widget.mount(row1, row2)

        # Total files
        total_box = Static(f"Total Files\n{stats['total_files']}", classes="stat-box total")
        
        # Pending
        pending_box = Static(f"Pending\n{stats['pending']}", classes="stat-box pending")
        
        # Approved
        approved_box = Static(f"Approved\n{stats['approved']}", classes="stat-box approved")
        
        # Progress percentage
        progress_box = Static(f"Progress\n{progress:.1f}%", classes="stat-box total")
        
        # Total choices
        choices_box = Static(f"Total Choices\n{stats['total_choices']}", classes="stat-box")
        
        # Rejected
        rejected_box = Static(f"Rejected\n{stats['rejected']}", classes="stat-box rejected")
        
        # Mount the boxes to the rows
        row1.mount(total_box, pending_box, approved_box)
        row2.mount(progress_box, choices_box, rejected_box)

        # Add shortcuts reminder
        shortcuts = Static(
            "Shortcuts: (p)lay, (s)top, (a)pprove, (r)eject, (n)ext, (1-3) context, (q)uit",
            classes="shortcuts",
        )
        stats_widget.mount(shortcuts)

    def load_next_file(self) -> None:
        """Load the next pending file for review."""
        self.current_file = self.db.get_next_pending_file()
        self.update_stats()

    def action_play(self) -> None:
        """Play the current TTS file."""
        if not self.current_file:
            return

        # Get the file path - TTS files are in the tts_dir, not the game path
        file_hash = Path(self.current_file["file_path"]).stem
        tts_file_path = os.path.join(self.tts_dir, f"{file_hash}.flac")

        # Show notification about the file being played
        self.notify(f"Playing TTS file: {file_hash}.flac", title="Audio Playback")

        # Try to play the file
        try:
            self.audio_player.play(tts_file_path)
        except Exception as e:
            self.notify(f"Error playing audio: {str(e)}", title="Playback Error")
            # Try finding the file - maybe it has a different extension?
            import glob

            possible_files = glob.glob(os.path.join(self.tts_dir, f"{file_hash}.*"))
            if possible_files:
                self.notify(
                    f"Found alternative files: {', '.join(Path(f).name for f in possible_files)}",
                    title="Debug",
                )
            else:
                self.notify(f"No files found in {self.tts_dir} for hash {file_hash}", title="Debug")

    def action_stop(self) -> None:
        """Stop the currently playing audio."""
        self.audio_player.stop()

    def action_approve(self) -> None:
        """Approve the current TTS file."""
        if self.current_file:
            self.db.update_file_status(self.current_file["id"], "approved")
            self.load_next_file()

    def action_reject(self) -> None:
        """Reject the current TTS file."""
        if self.current_file:
            self.db.update_file_status(self.current_file["id"], "rejected")
            self.load_next_file()

    def action_next(self) -> None:
        """Skip to the next file without changing status."""
        self.load_next_file()

    def action_play_context_1(self) -> None:
        """Play with 1 line of context before and after."""
        self._play_with_context(1)

    def action_play_context_2(self) -> None:
        """Play with 2 lines of context before and after."""
        self._play_with_context(2)

    def action_play_context_3(self) -> None:
        """Play with 3 lines of context before and after."""
        self._play_with_context(3)

    def _find_game_voice_file(self, filename: str, lineno: int) -> Optional[str]:
        """Try to find a voice file in the game folder.

        Args:
            filename: Script filename
            lineno: Line number

        Returns:
            Path to the voice file if found, None otherwise
        """
        import glob

        if not self.game_path:
            return None

        # Example path pattern: audio/voices/ch1/empty/princess/empty_p_20.flac
        # Try finding it based on common patterns in the game
        script_name = Path(filename).stem  # Get script name without extension

        # Try various patterns
        patterns = [
            os.path.join(self.game_path, "audio", "voices", "**", f"{script_name}_*.flac"),
            os.path.join(self.game_path, "audio", "voices", "**", f"{script_name}*.flac"),
            os.path.join(self.game_path, "audio", "**", f"{script_name}_*.flac"),
            os.path.join(self.game_path, "**", "audio", "**", f"{script_name}_*.flac"),
        ]

        for pattern in patterns:
            matching_files = glob.glob(pattern, recursive=True)
            if matching_files:
                # If we have line numbers in filenames, try to find the closest match
                for match in matching_files:
                    if f"_{lineno}." in match or f"_{lineno}_" in match:
                        return match

                # If no exact line match, return the first match
                return matching_files[0]

        return None

    def _play_with_context(self, context_lines: int) -> None:
        """Play with the specified number of context lines.

        Args:
            context_lines: Number of context lines to include
        """
        if not self.current_file:
            return

        # First check if we have a context file to play
        before_file = None
        after_file = None

        # Try to find context files from the game directory
        if context_lines > 0 and self.current_file["context_before"]:
            context_count = min(context_lines, len(self.current_file["context_before"]))
            context = self.current_file["context_before"][-context_count:]

            for ctx in reversed(context):
                if "character" in ctx and ctx["character"] == "Princess":
                    # Try to find the voice file for this context
                    before_file = self._find_game_voice_file(
                        self.current_file["filename"], ctx.get("lineno", 0)
                    )
                    if before_file:
                        self.notify(
                            f"Found context before: {os.path.basename(before_file)}\nPath: {before_file}",
                            title="Context",
                        )
                        break

        # Try to find context after
        if context_lines > 0 and self.current_file["context_after"]:
            context_count = min(context_lines, len(self.current_file["context_after"]))
            context = self.current_file["context_after"][:context_count]

            for ctx in context:
                if "character" in ctx and ctx["character"] == "Princess":
                    # Try to find the voice file for this context
                    after_file = self._find_game_voice_file(
                        self.current_file["filename"], ctx.get("lineno", 0)
                    )
                    if after_file:
                        self.notify(
                            f"Found context after: {os.path.basename(after_file)}\nPath: {after_file}",
                            title="Context",
                        )
                        break

        # Now play the sequence: before -> tts -> after
        try:
            if before_file:
                self.notify(
                    f"Playing context before\nPath: {before_file}", title="Context Playback"
                )
                self.audio_player.play(before_file)
                # Wait for audio to finish
                import time

                while (
                    self.audio_player.current_process
                    and self.audio_player.current_process.poll() is None
                ):
                    time.sleep(0.5)

            # Play the TTS file
            self.action_play()
            # Wait for audio to finish
            import time

            while (
                self.audio_player.current_process
                and self.audio_player.current_process.poll() is None
            ):
                time.sleep(0.5)

            if after_file:
                self.notify(f"Playing context after\nPath: {after_file}", title="Context Playback")
                self.audio_player.play(after_file)
        except Exception as e:
            self.notify(f"Error during context playback: {str(e)}", title="Playback Error")


def setup_tts_data(
    db_path: str, tts_dir: str, game_path: Optional[Union[str, Path]] = None
) -> None:
    """Set up the TTS database and scan for files.

    Args:
        db_path: Path to the SQLite database
        tts_dir: Directory containing TTS files
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
    """
    from princess.tts.extractor import extract_all_choices
    import os

    # Create database
    db = TTSDatabase(db_path)

    # Extract choices
    print("Extracting choices from scripts...")
    choices = extract_all_choices(game_path)
    print(f"Found {len(choices)} choices")

    # Import choices to database
    print("Importing choices to database...")
    db.import_choices(choices)

    # Check if TTS directory exists
    if not os.path.exists(tts_dir):
        print(f"\nWarning: TTS directory '{tts_dir}' does not exist. Creating it now.")
        os.makedirs(tts_dir, exist_ok=True)
        print(f"Created directory: {tts_dir}")
        print(
            f"Note: No TTS files found. You need to generate TTS files and place them in this directory."
        )
    else:
        # Scan TTS directory
        print(f"Scanning TTS directory: {tts_dir}")
        # Check if there are any .flac files in the directory
        flac_files = list(Path(tts_dir).glob("*.flac"))
        if not flac_files:
            print(f"No .flac files found in {tts_dir}. You need to generate TTS files first.")
        db.scan_tts_directory(tts_dir)

    # Print stats
    stats = db.get_stats()
    print("\nTTS Database Statistics:")
    print(f"Total choices: {stats['total_choices']}")
    print(f"Total TTS files: {stats['total_files']}")
    print(f"Pending: {stats['pending']}")
    print(f"Approved: {stats['approved']}")
    print(f"Rejected: {stats['rejected']}")

    if stats["total_files"] == 0:
        print("\nNo TTS files found in the database. Next steps:")
        print("1. Export choices with: princess-tts export")
        print("2. Generate TTS files using the exported JSON")
        print("3. Place the generated .flac files in the TTS directory")
        print("4. Run 'princess-tts setup' again to scan the TTS files")
        print("5. Label the TTS files with: princess-tts label")


def main():
    """Main entry point for the CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="TTS labeling tool for Slay the Princess")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export choices for TTS generation")
    export_parser.add_argument(
        "--output", "-o", default="choices_for_tts.json", help="Output JSON file"
    )
    export_parser.add_argument(
        "--game-path",
        "-g",
        default=None,
        help="Path to game directory. If not specified, uses GAME_PATH env variable",
    )

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up the TTS database and scan for files")
    setup_parser.add_argument("--db", default="tts_choices.db", help="Path to the SQLite database")
    setup_parser.add_argument(
        "--tts-dir", default="tts_files", help="Directory containing TTS files"
    )
    setup_parser.add_argument(
        "--game-path",
        "-g",
        default=None,
        help="Path to game directory. If not specified, uses GAME_PATH env variable",
    )

    # Label command
    label_parser = subparsers.add_parser("label", help="Start the TTS labeling interface")
    label_parser.add_argument("--db", default="tts_choices.db", help="Path to the SQLite database")
    label_parser.add_argument(
        "--tts-dir", default="tts_files", help="Directory containing TTS files"
    )
    label_parser.add_argument(
        "--game-path",
        "-g",
        default=None,
        help="Path to game directory. If not specified, uses GAME_PATH env variable",
    )

    args = parser.parse_args()

    if args.command == "export":
        from princess.tts.extractor import export_choices_for_tts

        export_choices_for_tts(args.output, args.game_path)

    elif args.command == "setup":
        setup_tts_data(args.db, args.tts_dir, args.game_path)

    elif args.command == "label":
        app = TTSLabelApp(args.db, args.tts_dir, args.game_path)
        app.run()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
