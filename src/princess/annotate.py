"""
Stage 5: Annotate audio files
Interactive CLI for annotating the choice audio files generated in the pipeline.
"""

import pickle
from enum import Enum
from pathlib import Path
import subprocess
import time
import audiofile
import numpy as np
import sounddevice
import typer
from rich.console import Console
from rich.table import Table
from sqlite_utils import Database
import pygame
import threading
import readchar
import queue

from princess.game import get_game_path
from princess.models import Dialogue
from princess.text import print_choice_context, strip_formatting
from princess.voice import generate_choice_audio

app = typer.Typer()
console = Console()

pygame.init()
pygame.mixer.init()


class SoundPlayer:
    """
    A non-blocking audio player that maintains a playlist and plays audio in a background thread.
    """

    def __init__(self):
        self.playlist = queue.Queue()
        self.current_file = None
        self.is_playing = False
        self.stop_requested = False
        self.thread = None

    def start(self):
        """Start the player thread if not already running."""
        if self.thread is None or not self.thread.is_alive():
            self.stop_requested = False
            self.thread = threading.Thread(target=self._player_thread)
            self.thread.daemon = True
            self.thread.start()

    def _player_thread(self):
        """Background thread that plays audio files from the playlist."""
        while not self.stop_requested:
            try:
                # Get the next file from the playlist if one is available
                try:
                    self.current_file = self.playlist.get(block=False)
                    self.is_playing = True

                    # Play the file
                    pygame.mixer.music.load(self.current_file)
                    pygame.mixer.music.play()

                    # Wait for playback to complete or stop request
                    while pygame.mixer.music.get_busy() and not self.stop_requested:
                        time.sleep(0.1)

                    self.is_playing = False
                    self.playlist.task_done()

                except queue.Empty:
                    # No files in playlist, sleep briefly and check again
                    time.sleep(0.2)

            except Exception as e:
                console.print(f"[red]Error in player thread: {e}[/]")
                self.is_playing = False
                time.sleep(0.5)  # Prevent busy-looping on error

    def queue(self, file_path):
        """Add a file to the playlist."""
        self.playlist.put(file_path)
        self.start()  # Ensure the player thread is running

    def queue_multiple(self, file_paths):
        """Add multiple files to the playlist."""
        for path in file_paths:
            self.playlist.put(path)
        self.start()  # Ensure the player thread is running

    def clear(self):
        """Clear the playlist and stop current playback."""
        self.stop()
        # Clear the queue
        while not self.playlist.empty():
            try:
                self.playlist.get(block=False)
                self.playlist.task_done()
            except queue.Empty:
                break

    def stop(self):
        """Stop the current playback but keep the thread alive."""
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False

    def shutdown(self):
        """Stop playback and terminate the player thread."""
        self.stop_requested = True
        self.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)


# Create a global sound player instance
sound_player = SoundPlayer()


class AnnotationStatus(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    SPECIAL = "special"
    PENDING = "pending"


def setup_db():
    """Set up the SQLite database for annotations using sqlite-utils."""
    db_path = Path("output/annotations.db")
    db = Database(db_path)

    # Create table if it doesn't exist
    if "annotations" not in db.table_names():
        db["annotations"].create({"filename": str, "status": str, "notes": str}, pk="filename")

        # Add default index on status
        db["annotations"].create_index(["status"])

        # Initialize with existing choices
        console.print("[cyan]New database created, initializing with existing choices...[/]")
        initialize_db_with_choices(db)
    else:
        # Check for new choices that aren't in the database yet
        update_db_with_new_choices(db)

    return db


def initialize_db_with_choices(db):
    """Initialize the database with all existing choices."""
    try:
        choices = load_choices()

        # Add each choice to the database with PENDING status
        rows = []
        for choice in choices.choices:
            if choice.output:
                rows.append(
                    {
                        "filename": choice.output.name,
                        "status": AnnotationStatus.PENDING,
                        "notes": None,
                    }
                )

        if rows:
            db["annotations"].insert_all(rows, pk="filename")
            console.print(f"[green]Initialized database with {len(rows)} choices[/]")
        else:
            console.print("[yellow]No choices found for initialization[/]")
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/]")


def update_db_with_new_choices(db):
    """Update the database with any new choices that aren't already in it."""
    try:
        choices = load_choices()

        # Get all existing filenames in the database
        existing_filenames = set(row["filename"] for row in db["annotations"].rows)

        # Find new choices that aren't in the database
        new_rows = []
        for choice in choices.choices:
            if choice.output and choice.output.name not in existing_filenames:
                new_rows.append(
                    {
                        "filename": choice.output.name,
                        "status": AnnotationStatus.PENDING,
                        "notes": None,
                    }
                )

        if new_rows:
            db["annotations"].insert_all(new_rows, pk="filename")
            console.print(f"[green]Added {len(new_rows)} new choices to the database[/]")
    except Exception as e:
        console.print(f"[red]Error updating database with new choices: {e}[/]")


def load_choices():
    """Load the choices data from the pickle file."""
    choices_path = Path("output/choices.pickle")
    if not choices_path.exists():
        console.print("[red]Error: choices.pickle file not found. Run the pipeline first.[/]")
        raise typer.Exit(1)

    with open(choices_path, "rb") as f:
        return pickle.load(f)


def display_annotation_progress(db):
    """Display the current annotation progress."""
    # Get total counts using sqlite-utils
    status_counts = {
        row["status"]: row["count"]
        for row in db.query(
            """
        SELECT 
            status, 
            COUNT(*) as count 
        FROM 
            annotations 
        GROUP BY 
            status
        """
        )
    }

    total = sum(status_counts.values())

    if total == 0:
        console.print("[yellow]No annotations found in the database yet.[/]")
        return

    approved = status_counts.get(AnnotationStatus.APPROVE, 0)
    rejected = status_counts.get(AnnotationStatus.REJECT, 0)
    special = status_counts.get(AnnotationStatus.SPECIAL, 0)
    pending = status_counts.get(AnnotationStatus.PENDING, 0)

    table = Table(title="Annotation Progress")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Percentage", style="green")

    table.add_row("Approved", str(approved), f"{approved / total * 100:.2f}%" if total else "0%")
    table.add_row("Rejected", str(rejected), f"{rejected / total * 100:.2f}%" if total else "0%")
    table.add_row("Special", str(special), f"{special / total * 100:.2f}%" if total else "0%")
    table.add_row("Pending", str(pending), f"{pending / total * 100:.2f}%" if total else "0%")
    table.add_row("Total", str(total), "100%")

    console.print(table)


def play_audio(audio_path, block=False):
    """
    Play audio using the global sound player.
    This function never blocks, regardless of the block parameter (kept for compatibility).
    """
    sound_player.clear()  # Clear any current playlist
    sound_player.queue(audio_path)


def play_context_and_choice(choice, previous_count=1):
    """Play previous context and the choice back to back."""
    # Get the previous dialogues based on the requested count
    prev_dialogues = choice.previous_dialogues[-previous_count:] if previous_count > 0 else []
    game_path = get_game_path()

    # Clear any current playlist
    sound_player.clear()

    if not prev_dialogues:
        # If no previous dialogues, just play the choice
        console.print("[yellow]No previous dialogues to play, playing choice only.[/]")
        sound_player.queue(choice.output)
        return

    console.print(
        f"[cyan]Playing {len(prev_dialogues)} previous dialogue(s) + choice + next dialogue if available...[/]"
    )

    # Prepare playlist of audio files
    playlist = []

    # Add previous dialogues to playlist
    for i, dialogue in enumerate(prev_dialogues):
        console.print(f"[dim cyan]Previous dialogue {i + 1}/{len(prev_dialogues)}:[/]")

        if isinstance(dialogue, Dialogue):
            text = f"{dialogue.character}: {strip_formatting(dialogue.dialogue)}"
            console.print(f"[dim]{text}[/]")

            # Add to playlist if voice file is available
            if dialogue.voice:
                voice_path = game_path / dialogue.voice
                playlist.append(voice_path)
            else:
                console.print("[yellow]No voice file for this dialogue[/]")
        else:
            # It's a Choice object
            text = f"Choice: {strip_formatting(dialogue.choice)}"
            console.print(f"[dim]{text}[/]")

    # Add the choice audio to playlist
    console.print(f"[cyan]Main choice: {strip_formatting(choice.choice)}[/]")
    playlist.append(choice.output)

    # Add the next dialogue to playlist if available
    if choice.subsequent_dialogues:
        next_dialogue = choice.subsequent_dialogues[0]
        console.print(f"[dim cyan]Next dialogue:[/]")
        text = f"{next_dialogue.character}: {strip_formatting(next_dialogue.dialogue)}"
        console.print(f"[dim]{text}[/]")

        # Add to playlist if voice file is available
        if next_dialogue.voice:
            voice_path = game_path / next_dialogue.voice
            playlist.append(voice_path)
        else:
            console.print("[yellow]No voice file for this dialogue[/]")

    # Queue all files for playback
    sound_player.queue_multiple(playlist)


def play_choice_and_next(choice):
    """Play the choice and the next dialogue if available."""
    game_path = get_game_path()

    # Clear any current playlist
    sound_player.clear()

    # Prepare playlist
    playlist = []

    # Add the choice audio to playlist
    console.print(f"[cyan]Main choice: {strip_formatting(choice.choice)}[/]")
    playlist.append(choice.output)

    # Add the next dialogue to playlist if available
    if choice.subsequent_dialogues:
        next_dialogue = choice.subsequent_dialogues[0]
        console.print(f"[dim cyan]Next dialogue:[/]")
        text = f"{next_dialogue.character}: {strip_formatting(next_dialogue.dialogue)}"
        console.print(f"[dim]{text}[/]")

        # Add to playlist if voice file is available
        if next_dialogue.voice:
            voice_path = game_path / next_dialogue.voice
            playlist.append(voice_path)
        else:
            console.print("[yellow]No voice file for this dialogue[/]")

    # Queue all files for playback
    sound_player.queue_multiple(playlist)


def save_annotation(db, filename, status, notes=None):
    """Save the annotation to the database using sqlite-utils."""
    db["annotations"].upsert(
        {"filename": filename, "status": status, "notes": notes}, pk="filename"
    )


def get_annotation_status(db, filename):
    """Get the current annotation status for a filename using sqlite-utils."""
    row = db["annotations"].get(filename)
    return row["status"] if row else AnnotationStatus.PENDING


def regenerate_audio(choice):
    """Regenerate the audio for a choice using the voice generation model."""
    try:
        console.print(f"[yellow]Regenerating audio for: {strip_formatting(choice.choice)}[/]")

        # Ensure we have clean text to generate
        if not choice.clean:
            console.print("[red]Error: No clean text available for this choice[/]")
            return False

        generate_choice_audio(choice, force=True)
        return True

    except Exception as e:
        console.print(f"[red]Error regenerating audio: {e}[/]")
        return False


def handle_command(cmd, db, filename, choice, context=None):
    """
    Handle a command from user input using pattern matching.
    Returns True if the command loop should continue, False if it should break.
    """
    match cmd:
        case "a":
            save_annotation(db, filename, AnnotationStatus.APPROVE)
            console.print("[green]Marked as APPROVED[/]")
            return False
        case "r":
            save_annotation(db, filename, AnnotationStatus.REJECT)
            console.print("[red]Marked as REJECTED[/]")
            return False
        case "s":
            notes = input("Enter notes for special case: ")
            save_annotation(db, filename, AnnotationStatus.SPECIAL, notes)
            console.print("[yellow]Marked as SPECIAL CASE[/]")
            return False
        case "p":
            console.print("\n[cyan]Playing choice audio...[/]")
            play_audio(choice.output)
            return True
        case "0":
            console.print("\n[cyan]Playing choice + next dialogue...[/]")
            play_choice_and_next(choice)
            return True
        case "1" | "2" | "3":
            play_count = int(cmd)
            console.print(f"\n[cyan]Playing with {play_count} previous line(s)...[/]")
            play_context_and_choice(choice, play_count)
            return True
        case "g":
            # Regenerate in place, staying in the same menu
            if regenerate_audio(choice):
                console.print("\n[cyan]Playing regenerated audio...[/]")
                play_audio(choice.output)
                save_annotation(db, filename, AnnotationStatus.PENDING)
                console.print("[green]Regenerated audio marked as PENDING for review.[/]")
            return True
        case "n":
            console.print("[dim]Moving to next choice...[/]")
            return False
        case "q":
            console.print("[yellow]Quitting annotation...[/]")
            sound_player.shutdown()
            raise typer.Exit()
        case readchar.key.BACKSPACE:
            sound_player.stop()
            sound_player.clear()
            console.print("[yellow]Playback stopped[/]")
            return True
        case _:
            console.print("[red]Invalid action.[/]")
            return True


def run_command_loop(db, filename, choice):
    """
    Run a command loop for user interaction with single keypress commands.
    Returns True if the loop completed normally, False if it should exit early.
    """
    # Setup menu display
    current_status = get_annotation_status(db, filename)

    console.print("\n[bold]Available actions:[/]")
    console.print("[cyan]a[/]: approve  [cyan]r[/]: reject  [cyan]s[/]: special case")
    console.print(
        "[cyan]p[/]: play choice  [cyan]0[/]: play with next line  [cyan]1-3[/]: play with n lines of context"
    )
    console.print("[cyan]g[/]: regenerate audio  [cyan]n[/]: next  [cyan]q[/]: quit")
    console.print("[cyan]backspace[/]: stop playback")

    while True:
        try:
            console.print("\nPress a key for action: ", end="")
            action = readchar.readkey()
            console.print(action)  # Echo the key pressed

            # Process the command
            should_continue = handle_command(action, db, filename, choice)
            if not should_continue:
                return True
        except KeyboardInterrupt:
            console.print("[yellow]\nQuitting annotation...[/]")
            sound_player.shutdown()
            raise typer.Exit()

    return True


@app.command()
def annotate(
    start_index: int = typer.Option(0, "--start", "-s", help="Starting index for annotation"),
    limit: int = typer.Option(
        None, "--limit", "-l", help="Limit the number of choices to annotate"
    ),
    pending_only: bool = typer.Option(
        False, "--pending", "-p", help="Only show pending annotations"
    ),
):
    """
    Interactive CLI for annotating audio files.
    """
    # Initialize the sound player
    sound_player.start()

    try:
        # Load data and setup database
        db = setup_db()
        choices = load_choices()

        # Display progress
        display_annotation_progress(db)

        # Filter choices based on options
        all_choices = choices.choices
        if pending_only:
            filtered_choices = []
            for choice in all_choices:
                if not choice.output:
                    continue
                filename = choice.output.name
                status = get_annotation_status(db, filename)
                if status == AnnotationStatus.PENDING:
                    filtered_choices.append(choice)
            working_choices = filtered_choices
        else:
            working_choices = [c for c in all_choices if c.output]

        # Apply start index and limit
        if limit:
            working_choices = working_choices[start_index : start_index + limit]
        else:
            working_choices = working_choices[start_index:]

        if not working_choices:
            console.print("[yellow]No choices to annotate based on your filters.[/]")
            return

        console.print(f"[green]Loaded {len(working_choices)} choices for annotation.[/]")

        # Annotation loop
        for i, choice in enumerate(working_choices):
            if not choice.output:
                console.print(
                    f"[yellow]Skipping choice {i + start_index} - no output path defined[/]"
                )
                continue

            if not choice.output.exists():
                console.print(f"[yellow]Audio file missing for choice {i + start_index}[/]")
                console.print("[cyan]Generating audio file automatically...[/]")
                generate_choice_audio(choice, force=True)
                console.print("[green]Successfully generated missing audio file[/]")
                save_annotation(db, choice.output.name, AnnotationStatus.PENDING)

            filename = choice.output.name
            current_status = get_annotation_status(db, filename)

            console.print(
                f"\n[bold cyan]Choice {i + start_index + 1}/{len(working_choices)} - Current status: {current_status}[/]"
            )
            console.print(f"[dim]File: {choice.output}[/]")

            # Show the dialogue context
            print_choice_context(choice)

            # Play choice audio
            console.print("\n[cyan]Playing choice audio...[/]")
            sound_player.clear()
            play_audio(choice.output)

            # Run the main command loop for this choice
            run_command_loop(db, filename, choice)

        # Final progress report
        console.print("\n[bold green]Annotation session completed![/]")
        display_annotation_progress(db)

    finally:
        # Make sure to shut down the player thread when the program exits
        sound_player.shutdown()


if __name__ == "__main__":
    app()
