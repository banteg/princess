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
        
        # Stop any currently playing audio
        self.stop()
        
        # Choose the appropriate command based on platform
        system = platform.system()
        if system == "Darwin":  # macOS
            cmd = ["afplay", file_path]
        elif system == "Linux":
            cmd = ["aplay", file_path]
        elif system == "Windows":
            cmd = ["start", "/b", "", file_path]
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
        
        # Start the process
        self.current_process = subprocess.Popen(cmd)
    
    def stop(self) -> None:
        """Stop the currently playing audio."""
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
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
    
    def __init__(self, db_path: str, tts_dir: str):
        """Initialize the app.
        
        Args:
            db_path: Path to the SQLite database
            tts_dir: Directory containing TTS files
        """
        super().__init__()
        self.db = TTSDatabase(db_path)
        self.tts_dir = tts_dir
        self.audio_player = AudioPlayer()
        
    def on_mount(self) -> None:
        """Load the next file when the app starts."""
        self.load_next_file()
        self.update_stats()
    
    def compose(self) -> ComposeResult:
        """Create the UI components."""
        yield Header(show_clock=True)
        
        with Container(id="main"):
            # Stats section
            with Container(id="stats-section"):
                yield Static("TTS Labeling Progress", classes="section-title")
                yield Static("", id="stats-content")
                
            # File info section
            with Container(id="file-section"):
                yield Static("Current File", classes="section-title")
                yield Static("", id="file-info")
                
            # Choice text section
            with Container(id="choice-section"):
                yield Static("Choice Text", classes="section-title")
                yield Static("", id="choice-text")
                yield Static("Clean TTS Text", classes="subsection-title")
                yield Static("", id="clean-tts-text")
                
            # Context section
            with Container(id="context-section"):
                yield Static("Context", classes="section-title")
                
                # Context before
                yield Static("Before:", classes="subsection-title")
                yield Static("", id="context-before")
                
                # Context after
                yield Static("After:", classes="subsection-title")
                yield Static("", id="context-after")
                
            # Controls section
            with Horizontal(id="controls-section"):
                yield Button("Play", id="play-btn", variant="primary")
                yield Button("Stop", id="stop-btn", variant="default")
                yield Button("Approve", id="approve-btn", variant="success")
                yield Button("Reject", id="reject-btn", variant="error")
                yield Button("Next", id="next-btn", variant="default")
        
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
            self.query_one("#file-info").update("No more files to label")
            self.query_one("#choice-text").update("")
            self.query_one("#clean-tts-text").update("")
            self.query_one("#context-before").update("")
            self.query_one("#context-after").update("")
            return
            
        # Update file info
        file_info = (
            f"ID: {file['id']}\n"
            f"File: {file['file_path']}\n"
            f"Status: {file['status']}\n"
            f"Source: {file['filename']}:{file['lineno']}\n"
        )
        self.query_one("#file-info").update(file_info)
        
        # Update choice text
        self.query_one("#choice-text").update(file["choice_text"])
        self.query_one("#clean-tts-text").update(file["clean_tts_text"])
        
        # Update context before
        context_before_text = ""
        for ctx in file["context_before"]:
            context_before_text += f"{ctx['character']}: {ctx['text']}\n"
        self.query_one("#context-before").update(context_before_text)
        
        # Update context after
        context_after_text = ""
        for ctx in file["context_after"]:
            context_after_text += f"{ctx['character']}: {ctx['text']}\n"
        self.query_one("#context-after").update(context_after_text)
    
    def update_stats(self) -> None:
        """Update the statistics display."""
        stats = self.db.get_stats()
        
        stats_text = (
            f"Total choices: {stats['total_choices']}\n"
            f"Total TTS files: {stats['total_files']}\n"
            f"Pending: {stats['pending']}\n"
            f"Approved: {stats['approved']}\n"
            f"Rejected: {stats['rejected']}\n"
            f"Progress: {(stats['approved'] + stats['rejected']) / stats['total_files'] * 100:.1f}% complete"
        )
        
        self.query_one("#stats-content").update(stats_text)
    
    def load_next_file(self) -> None:
        """Load the next pending file for review."""
        self.current_file = self.db.get_next_pending_file()
        self.update_stats()
    
    def action_play(self) -> None:
        """Play the current TTS file."""
        if self.current_file:
            self.audio_player.play(self.current_file["file_path"])
    
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
    
    def _play_with_context(self, context_lines: int) -> None:
        """Play with the specified number of context lines.
        
        Args:
            context_lines: Number of context lines to include
        """
        # This is a placeholder for a more advanced feature
        # In a real implementation, we would create a temporary audio file with
        # text-to-speech for the context lines, and play them in sequence
        # For now, we'll just play the choice TTS file
        self.action_play()
        
        # Display a message about the limitation
        self.notify(
            "Context playback is a placeholder. Currently, only the choice audio plays.", 
            title="Context Playback"
        )


def setup_tts_data(db_path: str, tts_dir: str, game_path: Optional[Union[str, Path]] = None) -> None:
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
        print(f"Note: No TTS files found. You need to generate TTS files and place them in this directory.")
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
    
    if stats['total_files'] == 0:
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
    export_parser.add_argument("--output", "-o", default="choices_for_tts.json", 
                               help="Output JSON file")
    export_parser.add_argument("--game-path", "-g", default=None, 
                               help="Path to game directory. If not specified, uses GAME_PATH env variable")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up the TTS database and scan for files")
    setup_parser.add_argument("--db", default="tts_choices.db", 
                              help="Path to the SQLite database")
    setup_parser.add_argument("--tts-dir", default="tts_files", 
                              help="Directory containing TTS files")
    setup_parser.add_argument("--game-path", "-g", default=None, 
                              help="Path to game directory. If not specified, uses GAME_PATH env variable")
    
    # Label command
    label_parser = subparsers.add_parser("label", help="Start the TTS labeling interface")
    label_parser.add_argument("--db", default="tts_choices.db", 
                             help="Path to the SQLite database")
    label_parser.add_argument("--tts-dir", default="tts_files", 
                             help="Directory containing TTS files")
    
    args = parser.parse_args()
    
    if args.command == "export":
        from princess.tts.extractor import export_choices_for_tts
        export_choices_for_tts(args.output, args.game_path)
    
    elif args.command == "setup":
        setup_tts_data(args.db, args.tts_dir, args.game_path)
    
    elif args.command == "label":
        app = TTSLabelApp(args.db, args.tts_dir)
        app.run()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
