"""CLI tool for labeling TTS generated from choices."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Container, Horizontal
from textual.binding import Binding
from textual.reactive import reactive

from princess.tts.database import TTSDatabase

# Set up logging to file and console
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_debug.log")

# Create logger
logger = logging.getLogger("tts_app")
logger.setLevel(logging.INFO)
logger.propagate = False  # Don't propagate to root logger

# File handler for debug log
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Console handler for terminal output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(message)s"))

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class AudioPlayer:
    """Non-blocking audio player for various audio formats."""

    def __init__(self):
        """Initialize the audio player."""
        self.current_process = None
        # Flag to ensure we're not waiting on a process
        self.is_playing = False
        import threading

        self._playback_thread = None

    def play(self, file_path: str) -> None:
        """Play an audio file asynchronously.

        Args:
            file_path: Path to the audio file
        """
        import subprocess
        import platform
        import os
        import pathlib
        import threading

        # Check if file exists
        if not os.path.exists(file_path):
            error_msg = f"Audio file not found: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Stop any currently playing audio
        self.stop()

        # Get file extension
        file_ext = pathlib.Path(file_path).suffix.lower()

        # Choose the appropriate command based on platform and file type
        system = platform.system()
        if system == "Darwin":  # macOS
            # afplay works for various audio formats on macOS
            cmd = ["afplay", file_path]
        elif system == "Linux":
            # Choose player based on file extension
            if file_ext in [".wav", ".flac"]:
                cmd = ["aplay", file_path]
            elif file_ext in [".mp3", ".ogg"]:
                cmd = ["mpg123", file_path]
            else:
                # Fallback to aplay
                cmd = ["aplay", file_path]
        elif system == "Windows":
            # Use START to launch a non-blocking process on Windows
            cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{file_path}').Play();"]
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

        # Debug information
        file_exists = os.path.exists(file_path)
        file_size = os.path.getsize(file_path) if file_exists else 0
        logger.info(f"Playing audio file: {file_path}")
        logger.info(f"File exists: {file_exists}, File size: {file_size} bytes")
        logger.info(f"Command: {' '.join(cmd)}")

        # Start the process in a separate thread to avoid blocking the UI
        def _play_in_thread():
            try:
                self.is_playing = True
                self.current_process = subprocess.Popen(cmd)
                logger.info(f"Started playback process for {file_path}")
                # Wait for process to complete but don't block the app
                return_code = self.current_process.wait()
                self.is_playing = False
                logger.info(
                    f"Playback of {os.path.basename(file_path)} completed with return code {return_code}"
                )
            except Exception as e:
                logger.error(f"Error playing audio: {str(e)}")
                logger.error(f"Command attempted: {' '.join(cmd)}")
                # Check if the file has the right extension but wrong format
                if file_exists and file_size > 0:
                    logger.error(
                        f"File exists but might have wrong format. File extension: {file_ext}"
                    )
                self.is_playing = False

        # Create and start a new thread
        self._playback_thread = threading.Thread(target=_play_in_thread)
        self._playback_thread.daemon = True  # Thread will die when app exits
        self._playback_thread.start()
        logger.info(f"Started playback thread for {os.path.basename(file_path)}")

    def stop(self) -> None:
        """Stop the currently playing audio."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                logger.info("Stopped audio playback")
                self.is_playing = False
            except Exception as e:
                logger.error(f"Error stopping audio: {str(e)}")
            finally:
                self.current_process = None


class TTSLabelApp(App):
    """Textual TUI app for labeling TTS files."""

    # Load custom CSS
    CSS_PATH = Path(__file__).parent / "tts_label.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_play", "Play/Pause audio"),
        Binding("0", "play_context_choice", "Play 1 line before + choice"),
        Binding("1", "play_context_1", "Play with 1 line context"),
        Binding("2", "play_context_2", "Play with 2 lines context"),
        Binding("3", "play_context_3", "Play with 3 lines context"),
        Binding("y", "approve", "Approve"),
        Binding("n", "reject", "Reject"),
        Binding("t", "next", "Next file"),
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
                yield Button("Play (space)", id="play-btn", variant="primary")
                yield Button("Context (0)", id="context-btn", variant="default")
                yield Button("Approve (y)", id="approve-btn", variant="success")
                yield Button("Reject (n)", id="reject-btn", variant="error")
                yield Button("Next (t)", id="next-btn", variant="default")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        logger.info(f"Button pressed: {button_id}")

        if button_id == "play-btn":
            self.action_toggle_play()
        elif button_id == "context-btn":
            self.action_play_context_choice()
        elif button_id == "approve-btn":
            self.action_approve()
        elif button_id == "reject-btn":
            self.action_reject()
        elif button_id == "next-btn":
            logger.info("Next button pressed")
            self.notify("Next button pressed", title="Next")
            self.action_next()  # Use action_next instead

    def _create_context_line(
        self,
        character: str,
        text: Union[str, Dict[str, Any]],
        filename: str,
        lineno: int,
        voice_path: Optional[str] = None,
    ) -> Static:
        """Create a styled context line widget.

        Args:
            character: Character name
            text: Line text or context dictionary
            filename: Script filename
            lineno: Line number
            voice_path: Optional path to voice file

        Returns:
            A Static widget with the context line
        """
        from textual.widgets import Static

        # Create main content
        content_parts = []

        # Extract the actual text display
        display_text = text["text"] if isinstance(text, dict) else text
        content_parts.append(f"{character}: {display_text}")

        # Try to get voice path from the context
        direct_voice = None
        if isinstance(text, dict) and "voice" in text and text["voice"]:
            direct_voice = text["voice"]
            logger.info(f"Found voice path in context data: {direct_voice}")
            # If voice path is relative, make it absolute
            if not os.path.isabs(direct_voice):
                absolute_path = os.path.join(self.game_path, direct_voice)
                if os.path.exists(absolute_path):
                    direct_voice = absolute_path
                    logger.info(f"Using absolute voice path: {direct_voice}")
                else:
                    logger.warning(f"Voice file doesn't exist at expected path: {absolute_path}")

        # Add voice file info
        if direct_voice and os.path.exists(direct_voice):
            # Use the direct voice path from context
            audio_file = os.path.basename(direct_voice)
            content_parts.append(f"Voice: [dim]{audio_file}[/dim]")
            logger.info(f"Using direct voice file: {direct_voice}")
        elif voice_path and os.path.exists(voice_path):
            # Use the found voice path
            audio_file = os.path.basename(voice_path)
            content_parts.append(f"Voice: [dim]{audio_file}[/dim]")
            logger.info(f"Using found voice file: {voice_path}")

        # Join parts with newlines
        content = "\n".join(content_parts)

        # Direct output for debugging
        logger.info(f"Context line content: {content}")

        # Return a static widget with the content and appropriate classes
        return Static(content, classes="context-line")

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
                # Try to find the voice file path
                voice_path = None
                if "lineno" in ctx:
                    voice_path = self._find_game_voice_file(file["filename"], ctx.get("lineno", 0))

                # Create a styled context line with the voice file path
                # Pass the whole context object to handle 'voice' paths directly
                ctx_static = self._create_context_line(
                    character=ctx["character"],
                    text=ctx,  # Pass the whole context object
                    filename=file["filename"],
                    lineno=ctx.get("lineno", 0),
                    voice_path=voice_path,
                )
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
                # Try to find the voice file path
                voice_path = None
                if "lineno" in ctx:
                    voice_path = self._find_game_voice_file(file["filename"], ctx.get("lineno", 0))

                # Create a styled context line with the voice file path
                # Pass the whole context object to handle 'voice' paths directly
                ctx_static = self._create_context_line(
                    character=ctx["character"],
                    text=ctx,  # Pass the whole context object
                    filename=file["filename"],
                    lineno=ctx.get("lineno", 0),
                    voice_path=voice_path,
                )
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
            approved_percent = stats["approved"] / stats["total_files"] * 100
            rejected_percent = stats["rejected"] / stats["total_files"] * 100
            pending_percent = stats["pending"] / stats["total_files"] * 100
        else:
            progress = approved_percent = rejected_percent = pending_percent = 0

        # Clear existing stats content
        stats_widget = self.query_one("#stats-display")
        stats_widget.remove_children()

        # Create compact progress stats layout
        main_row = Horizontal(classes="main-stat-row")
        stats_widget.mount(main_row)
        
        # Overall progress
        overall_label = Static(f"Overall: {stats['approved'] + stats['rejected']}/{stats['total_files']} ({progress:.1f}%)", classes="stat-label")
        overall_bar = ProgressBar(total=100, show_percentage=False, classes="compact-progress")
        overall_bar.update(progress=progress)
        main_row.mount(overall_label)
        main_row.mount(overall_bar)
        
        # Create rows for each stat type
        approved_row = Horizontal(classes="stat-row")
        rejected_row = Horizontal(classes="stat-row")
        pending_row = Horizontal(classes="stat-row")
        stats_widget.mount(approved_row, rejected_row, pending_row)
        
        # Approved
        approved_label = Static(f"Approved: {stats['approved']}", classes="stat-label approved")
        approved_bar = ProgressBar(total=100, show_percentage=False, classes="compact-progress approved-bar")
        approved_bar.update(progress=approved_percent)
        approved_row.mount(approved_label)
        approved_row.mount(approved_bar)
        
        # Rejected
        rejected_label = Static(f"Rejected: {stats['rejected']}", classes="stat-label rejected")
        rejected_bar = ProgressBar(total=100, show_percentage=False, classes="compact-progress rejected-bar")
        rejected_bar.update(progress=rejected_percent)
        rejected_row.mount(rejected_label)
        rejected_row.mount(rejected_bar)
        
        # Pending
        pending_label = Static(f"Pending: {stats['pending']}", classes="stat-label pending")
        pending_bar = ProgressBar(total=100, show_percentage=False, classes="compact-progress pending-bar")
        pending_bar.update(progress=pending_percent)
        pending_row.mount(pending_label)
        pending_row.mount(pending_bar)

        # Add shortcuts reminder
        shortcuts = Static(
            "Shortcuts: space play/pause, 0 context+choice, 1-3 context, y approve, n reject, t next, q quit",
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
        # This is now triggered by 't' key
        logger.info("Next action triggered")
        self.notify("Loading next file...", title="Next")
        self.load_next_file()

    def action_toggle_play(self) -> None:
        """Toggle between play and pause."""
        if self.audio_player.is_playing:
            self.action_stop()
        else:
            self.action_play()

    def action_play_context_choice(self) -> None:
        """Play the last line before the choice and the choice itself."""
        # This will play 1 line before, but not the line after
        if self.current_file and self.current_file.get("context_before"):
            self._play_with_context(1, play_after=False)
        else:
            # If no context, just play the current file
            self.action_play()

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
            logger.info("Game path not set, can't search for voice files")
            return None

        # Get script name without extension
        script_name = Path(filename).stem
        logger.info(f"Script name: {script_name}, Line: {lineno}")

        # Try multiple common locations and formats for voice files
        potential_paths = []

        # Common audio formats
        formats = ["ogg", "mp3", "wav", "flac"]

        # Try exact line matches first
        for fmt in formats:
            # Direct path with line number (different patterns)
            potential_paths.extend(
                [
                    os.path.join(self.game_path, f"{script_name}_{lineno}.{fmt}"),
                    os.path.join(self.game_path, f"{script_name}-{lineno}.{fmt}"),
                    os.path.join(self.game_path, f"{script_name}{lineno}.{fmt}"),
                ]
            )

            # Voice subdirectory
            potential_paths.extend(
                [
                    os.path.join(self.game_path, "voice", f"{script_name}_{lineno}.{fmt}"),
                    os.path.join(self.game_path, "Voice", f"{script_name}_{lineno}.{fmt}"),
                ]
            )

            # Audio voice subdirectory
            potential_paths.extend(
                [
                    os.path.join(self.game_path, "audio", "voice", f"{script_name}_{lineno}.{fmt}"),
                    os.path.join(self.game_path, "Audio", "Voice", f"{script_name}_{lineno}.{fmt}"),
                ]
            )

            # Game audio voice subdirectory
            potential_paths.extend(
                [
                    os.path.join(
                        self.game_path, "game", "audio", "voice", f"{script_name}_{lineno}.{fmt}"
                    ),
                    os.path.join(
                        self.game_path, "Game", "Audio", "Voice", f"{script_name}_{lineno}.{fmt}"
                    ),
                ]
            )

        # Log total search paths
        logger.info(f"Trying {len(potential_paths)} potential voice file locations")

        # Check all potential paths
        for voice_path in potential_paths:
            logger.info(f"Looking for voice file: {voice_path}")
            if os.path.exists(voice_path):
                logger.info(f"FOUND voice file: {voice_path}")
                return voice_path

        # If not found by exact path, try using glob to find any matching files
        logger.info("No exact matches found, trying glob patterns...")

        glob_patterns = [
            os.path.join(self.game_path, "**", f"{script_name}*{lineno}*.ogg"),
            os.path.join(self.game_path, "**", f"{script_name}*{lineno}*.mp3"),
            os.path.join(self.game_path, "**", f"{script_name}*{lineno}*.wav"),
            os.path.join(self.game_path, "**", f"{script_name}*{lineno}*.flac"),
            os.path.join(self.game_path, "**", f"*{script_name}*{lineno}*.ogg"),
            os.path.join(self.game_path, "**", f"*voice*", f"*{script_name}*{lineno}*.ogg"),
        ]

        for pattern in glob_patterns:
            logger.info(f"Trying glob pattern: {pattern}")
            matches = glob.glob(pattern, recursive=True)
            if matches:
                logger.info(f"Found {len(matches)} matches with pattern {pattern}")
                for match in matches:
                    logger.info(f"Match: {match}")
                # Return the first match
                logger.info(f"Using first match: {matches[0]}")
                return matches[0]

        # If we still can't find anything, try a last resort - look for any voice files for this script
        logger.warning(f"Last resort: looking for any voice files for script {script_name}")
        last_resort_pattern = os.path.join(self.game_path, "**", f"*{script_name}*.ogg")
        matches = glob.glob(last_resort_pattern, recursive=True)
        if matches:
            logger.info(f"Found {len(matches)} matches with pattern {last_resort_pattern}")
            for match in matches:
                logger.info(f"Match: {match}")
            # Return the first match
            logger.info(f"Using first match: {matches[0]}")
            return matches[0]

        # If not found, log and return None
        logger.warning(
            f"Voice file not found for script {script_name}, line {lineno} after exhaustive search"
        )
        return None

    def _play_with_context(self, context_lines: int, play_after: bool = True) -> None:
        """Play with the specified number of context lines.

        Args:
            context_lines: Number of context lines to include
            play_after: Whether to play the line after the choice
        """
        import threading

        if not self.current_file:
            logger.warning("No current file loaded, can't play context")
            return

        # Log current file info for debugging
        logger.info(f"Current file: {self.current_file['file_path']}")
        logger.info(f"Script: {self.current_file['filename']}")
        logger.info(f"Line: {self.current_file['lineno']}")
        logger.info(f"Game path: {self.game_path}")

        # First check if we have a context file to play
        before_file = None
        after_file = None

        # Try to find context files from the game directory
        if context_lines > 0 and self.current_file["context_before"]:
            context_count = min(context_lines, len(self.current_file["context_before"]))
            context = self.current_file["context_before"][-context_count:]
            logger.info(f"Looking for context before ({len(context)} lines)")

            for i, ctx in enumerate(reversed(context)):
                logger.info(f"Context before #{i + 1}: {ctx}")

                # First check if the context has a voice field directly (as shown in logs)
                if "voice" in ctx and ctx["voice"]:
                    voice_path = ctx["voice"]
                    # If voice path is relative, make it absolute
                    if not os.path.isabs(voice_path):
                        voice_path = os.path.join(self.game_path, voice_path)

                    logger.info(f"Found direct voice path in context: {voice_path}")

                    if os.path.exists(voice_path):
                        before_file = voice_path
                        self.notify(
                            f"Found context before voice: {os.path.basename(before_file)}",
                            title="Context",
                        )
                        logger.info(
                            f"SUCCESS! Using direct voice file for context before: {before_file}"
                        )
                        break
                    else:
                        logger.warning(f"Direct voice file doesn't exist: {voice_path}")

                # Fallback to searching by character and line number
                if "character" in ctx:
                    logger.info(f"Checking line for character: {ctx.get('character', '')}")
                    logger.info(f"Line text: {ctx.get('text', '')}")

                    # Try to find the voice file for this context
                    before_file = self._find_game_voice_file(
                        self.current_file["filename"], ctx.get("lineno", 0)
                    )
                    if before_file:
                        self.notify(
                            f"Found context before: {os.path.basename(before_file)}\nPath: {before_file}",
                            title="Context",
                        )
                        logger.info(f"SUCCESS! Found voice file for context before: {before_file}")
                        break
                    else:
                        logger.warning(
                            f"No voice file found for context before, character: {ctx.get('character', 'unknown')}, line: {ctx.get('lineno', 0)}"
                        )

        # Try to find context after
        if context_lines > 0 and self.current_file["context_after"]:
            # Make sure we get the correct number of lines
            context_count = min(context_lines, len(self.current_file["context_after"]))
            context = self.current_file["context_after"][:context_count]
            logger.info(
                f"Looking for context after ({len(context)} lines) from {context_lines} requested"
            )

            for i, ctx in enumerate(context):
                logger.info(f"Context after #{i + 1}: {ctx}")

                # First check if the context has a voice field directly
                if "voice" in ctx and ctx["voice"]:
                    voice_path = ctx["voice"]
                    # If voice path is relative, make it absolute
                    if not os.path.isabs(voice_path):
                        voice_path = os.path.join(self.game_path, voice_path)

                    logger.info(f"Found direct voice path in context: {voice_path}")

                    if os.path.exists(voice_path):
                        after_file = voice_path
                        self.notify(
                            f"Found context after voice: {os.path.basename(after_file)}",
                            title="Context",
                        )
                        logger.info(
                            f"SUCCESS! Using direct voice file for context after: {after_file}"
                        )
                        break
                    else:
                        logger.warning(f"Direct voice file doesn't exist: {voice_path}")

                # Fallback to searching by character and line number
                if "character" in ctx:
                    logger.info(f"Checking line for character: {ctx.get('character', '')}")
                    logger.info(f"Line text: {ctx.get('text', '')}")

                    # Try to find the voice file for this context
                    after_file = self._find_game_voice_file(
                        self.current_file["filename"], ctx.get("lineno", 0)
                    )
                    if after_file:
                        self.notify(
                            f"Found context after: {os.path.basename(after_file)}\nPath: {after_file}",
                            title="Context",
                        )
                        logger.info(f"SUCCESS! Found voice file for context after: {after_file}")
                        break
                    else:
                        logger.warning(
                            f"No voice file found for context after, character: {ctx.get('character', 'unknown')}, line: {ctx.get('lineno', 0)}"
                        )

        # Import needed modules
        import time
        import threading

        # Create a function to play audio files in sequence with closure to capture play_after
        def play_sequence():
            nonlocal play_after  # Ensure play_after is accessible in the closure
            try:
                # Play before context
                if before_file:
                    logger.info(f"Starting sequence - Playing context before: {before_file}")
                    self.notify(
                        f"Playing context before\nPath: {os.path.basename(before_file)}",
                        title="Context Playback",
                    )
                    try:
                        # Play and wait for completion
                        self.audio_player.play(before_file)
                        while self.audio_player.is_playing:
                            time.sleep(0.1)
                        logger.info("Before context playback completed")
                    except Exception as e:
                        logger.error(f"Error playing before context: {str(e)}")
                        self.notify(
                            f"Error playing before context: {str(e)}", title="Playback Error"
                        )

                # Brief pause between audio files
                time.sleep(0.1)

                # Play the TTS file
                logger.info("Playing TTS file")
                self.action_play()
                # Wait for TTS to complete
                while self.audio_player.is_playing:
                    time.sleep(0.1)
                logger.info("TTS playback completed")

                # Only play after context if requested
                if play_after and after_file:
                    # Brief pause between audio files
                    time.sleep(0.1)

                    # Play after context
                    logger.info(f"Playing context after: {after_file}")
                    self.notify(
                        f"Playing context after\nPath: {os.path.basename(after_file)}",
                        title="Context Playback",
                    )
                    try:
                        # Play and wait for completion
                        self.audio_player.play(after_file)
                        while self.audio_player.is_playing:
                            time.sleep(0.1)
                        logger.info("After context playback completed")
                    except Exception as e:
                        logger.error(f"Error playing after context: {str(e)}")
                        self.notify(
                            f"Error playing after context: {str(e)}", title="Playback Error"
                        )

                logger.info("Audio sequence complete")

            except Exception as e:
                logger.error(f"Error during context playback sequence: {str(e)}")
                self.notify(f"Error during context playback: {str(e)}", title="Playback Error")

        # Start playback sequence in a separate thread to avoid blocking UI
        # Directly passing play_after is not needed since we use nonlocal to capture it
        sequence_thread = threading.Thread(target=play_sequence)
        sequence_thread.daemon = True
        sequence_thread.start()
        logger.info(f"Started audio sequence playback thread (play_after={play_after})")


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
    logger.info("Extracting choices from scripts...")
    choices = extract_all_choices(game_path)
    logger.info(f"Found {len(choices)} choices")

    # Import choices to database
    logger.info("Importing choices to database...")
    db.import_choices(choices)

    # Check if TTS directory exists
    if not os.path.exists(tts_dir):
        logger.warning(f"TTS directory '{tts_dir}' does not exist. Creating it now.")
        os.makedirs(tts_dir, exist_ok=True)
        logger.info(f"Created directory: {tts_dir}")
        logger.info(
            f"Note: No TTS files found. You need to generate TTS files and place them in this directory."
        )
    else:
        # Scan TTS directory
        logger.info(f"Scanning TTS directory: {tts_dir}")
        # Check if there are any .flac files in the directory
        flac_files = list(Path(tts_dir).glob("*.flac"))
        if not flac_files:
            logger.warning(
                f"No .flac files found in {tts_dir}. You need to generate TTS files first."
            )
        db.scan_tts_directory(tts_dir)

    # Log stats
    stats = db.get_stats()
    logger.info("\nTTS Database Statistics:")
    logger.info(f"Total choices: {stats['total_choices']}")
    logger.info(f"Total TTS files: {stats['total_files']}")
    logger.info(f"Pending: {stats['pending']}")
    logger.info(f"Approved: {stats['approved']}")
    logger.info(f"Rejected: {stats['rejected']}")

    if stats["total_files"] == 0:
        logger.info("\nNo TTS files found in the database. Next steps:")
        logger.info("1. Export choices with: princess-tts export")
        logger.info("2. Generate TTS files using the exported JSON")
        logger.info("3. Place the generated .flac files in the TTS directory")
        logger.info("4. Run 'princess-tts setup' again to scan the TTS files")
        logger.info("5. Label the TTS files with: princess-tts label")


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
