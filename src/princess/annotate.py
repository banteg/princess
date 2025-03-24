"""
Stage 5: Annotate audio files
Interactive CLI for annotating the choice audio files generated in the pipeline.
"""

import pickle
from enum import Enum
from pathlib import Path

import audiofile
import numpy as np
import sounddevice
import typer
from rich.console import Console
from rich.table import Table
from sqlite_utils import Database

from princess.game import get_game_path
from princess.models import Dialogue
from princess.text import print_choice_context, strip_formatting

app = typer.Typer()
console = Console()


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
        db["annotations"].create({
            "filename": str,
            "status": str,
            "notes": str
        }, pk="filename")
        
        # Add default index on status
        db["annotations"].create_index(["status"])
    
    return db


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
    status_counts = {row["status"]: row["count"] for row in db.query(
        """
        SELECT 
            status, 
            COUNT(*) as count 
        FROM 
            annotations 
        GROUP BY 
            status
        """
    )}
    
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
    
    table.add_row("Approved", str(approved), f"{approved/total*100:.1f}%" if total else "0%")
    table.add_row("Rejected", str(rejected), f"{rejected/total*100:.1f}%" if total else "0%")
    table.add_row("Special", str(special), f"{special/total*100:.1f}%" if total else "0%")
    table.add_row("Pending", str(pending), f"{pending/total*100:.1f}%" if total else "0%")
    table.add_row("Total", str(total), "100%")
    
    console.print(table)


def play_audio(audio_path):
    """Play the audio file."""
    try:
        if audio_path is None:
            console.print("[yellow]No audio file specified[/]")
            return
            
        path = Path(audio_path) if not isinstance(audio_path, Path) else audio_path
        
        if not path.exists():
            console.print(f"[yellow]Audio file not found: {path}[/]")
            return
            
        console.print(f"[dim]Playing: {path}[/]")
        data, sample_rate = audiofile.read(path)
        sounddevice.play(data, sample_rate)
        sounddevice.wait()
    except Exception as e:
        console.print(f"[red]Error playing audio: {e}[/]")


def play_context_and_choice(choice, previous_count=1):
    """Play previous context and the choice back to back."""
    try:
        import time
        
        # Get the previous dialogues based on the requested count
        prev_dialogues = choice.previous_dialogues[-previous_count:] if previous_count > 0 else []
        
        if not prev_dialogues:
            # If no previous dialogues, just play the choice
            console.print("[yellow]No previous dialogues to play, playing choice only.[/]")
            play_audio(choice.output)
            return
            
        console.print(f"[cyan]Playing {len(prev_dialogues)} previous dialogue(s) + choice...[/]")
        
        # Play a beep to indicate start
        play_beep(880, 0.3)
        time.sleep(0.5)  # Short pause
        
        game_path = get_game_path()
        
        # Play each dialogue sequentially
        for i, dialogue in enumerate(prev_dialogues):
            console.print(f"[dim cyan]Previous dialogue {i+1}/{len(prev_dialogues)}:[/]")
            
            if isinstance(dialogue, Dialogue):
                text = f"{dialogue.character}: {strip_formatting(dialogue.dialogue)}"
                console.print(f"[dim]{text}[/]")
                
                # Use the existing voice file if available
                voice_path = None
                if dialogue.voice:
                    voice_path = game_path / dialogue.voice
                    play_audio(voice_path)
                else:
                    console.print("[yellow]No voice file for this dialogue[/]")
                    play_beep(440, 1.0)  # Play tone as placeholder
            else:
                # It's a Choice object
                text = f"Choice: {strip_formatting(dialogue.choice)}"
                console.print(f"[dim]{text}[/]")
                play_beep(660, 0.8)  # Different tone for choices
                
            time.sleep(0.5)  # Short pause between dialogues
            
        # Play a separator beep before the choice
        play_beep(880, 0.3)
        time.sleep(0.5)  # Short pause
        
        # Play the choice audio
        console.print(f"[cyan]Main choice: {strip_formatting(choice.choice)}[/]")
        play_audio(choice.output)
        
    except Exception as e:
        console.print(f"[red]Error playing context audio: {e}[/]")


def play_beep(frequency=440, duration=0.3):
    """Play a simple beep tone."""
    sample_rate = 24000
    t = np.linspace(0, duration, int(duration * sample_rate), False)
    tone = 0.3 * np.sin(2 * np.pi * frequency * t)
    sounddevice.play(tone, sample_rate)
    sounddevice.wait()


def save_annotation(db, filename, status, notes=None):
    """Save the annotation to the database using sqlite-utils."""
    db["annotations"].upsert({
        "filename": filename,
        "status": status,
        "notes": notes
    }, pk="filename")


def get_annotation_status(db, filename):
    """Get the current annotation status for a filename using sqlite-utils."""
    row = db["annotations"].get(filename)
    return row["status"] if row else AnnotationStatus.PENDING


@app.command()
def annotate(
    start_index: int = typer.Option(0, "--start", "-s", help="Starting index for annotation"),
    limit: int = typer.Option(None, "--limit", "-l", help="Limit the number of choices to annotate"),
    pending_only: bool = typer.Option(False, "--pending", "-p", help="Only show pending annotations"),
):
    """
    Interactive CLI for annotating audio files.
    """
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
        working_choices = working_choices[start_index:start_index+limit]
    else:
        working_choices = working_choices[start_index:]
    
    if not working_choices:
        console.print("[yellow]No choices to annotate based on your filters.[/]")
        return
    
    console.print(f"[green]Loaded {len(working_choices)} choices for annotation.[/]")
    
    # Annotation loop
    for i, choice in enumerate(working_choices):
        if not choice.output or not choice.output.exists():
            console.print(f"[yellow]Skipping choice {i+start_index} - no audio file[/]")
            continue
            
        filename = choice.output.name
        current_status = get_annotation_status(db, filename)
        
        console.print(f"\n[bold cyan]Choice {i+start_index+1}/{len(working_choices)} - Current status: {current_status}[/]")
        console.print(f"[dim]File: {choice.output}[/]")
        
        # Show the dialogue context
        print_choice_context(choice)
        
        # Play choice audio
        console.print("\n[cyan]Playing choice audio...[/]")
        play_audio(choice.output)
        
        # Menu for actions
        while True:
            action = typer.prompt(
                "\nChoose action",
                type=typer.Choice(["a", "r", "s", "p1", "p2", "p3", "n", "q"]),
                help=(
                    "a: approve, r: reject, s: special case, "
                    "p1-3: play with 1-3 previous lines, n: next, q: quit"
                ),
                default="a" if current_status == AnnotationStatus.PENDING else "n"
            )
            
            if action == "a":
                save_annotation(db, filename, AnnotationStatus.APPROVE)
                console.print("[green]Marked as APPROVED[/]")
                break
            elif action == "r":
                save_annotation(db, filename, AnnotationStatus.REJECT)
                console.print("[red]Marked as REJECTED[/]")
                break
            elif action == "s":
                notes = typer.prompt("Enter notes for special case")
                save_annotation(db, filename, AnnotationStatus.SPECIAL, notes)
                console.print("[yellow]Marked as SPECIAL CASE[/]")
                break
            elif action == "p1":
                console.print("\n[cyan]Playing with 1 previous line...[/]")
                play_context_and_choice(choice, 1)
            elif action == "p2":
                console.print("\n[cyan]Playing with 2 previous lines...[/]")
                play_context_and_choice(choice, 2)
            elif action == "p3":
                console.print("\n[cyan]Playing with 3 previous lines...[/]")
                play_context_and_choice(choice, 3)
            elif action == "n":
                console.print("[dim]Skipping to next choice...[/]")
                break
            elif action == "q":
                console.print("[yellow]Quitting annotation...[/]")
                return
    
    # Final progress report
    console.print("\n[bold green]Annotation session completed![/]")
    display_annotation_progress(db)


if __name__ == "__main__":
    app() 
