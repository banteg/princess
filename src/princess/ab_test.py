"""
Stage 6: A/B Test Voice Choices
Interactive CLI for comparing two sets of generated voice files for choices.
"""

import pickle
import random
import time
from enum import Enum
from pathlib import Path

import readchar
import rich
import typer
from rich.console import Console
from rich.table import Table
from sqlite_utils import Database

# Reuse SoundPlayer and context printing from annotate
from princess.annotate import SoundPlayer, print_choice_context, load_choices
from princess.models import ChoiceResult
from princess.text import strip_formatting

app = typer.Typer(pretty_exceptions_show_locals=False)
console = Console()

# Create a global sound player instance for this module
sound_player = SoundPlayer()

# --- Database Setup ---

DB_PATH = Path("output/annotations.db")


class Preference(str, Enum):
    SET_A = "A"
    SET_B = "B"
    REJECT = "reject"
    PENDING = "pending"


def setup_ab_db() -> Database:
    """Set up the SQLite database and ensure the ab_results table exists."""
    db = Database(DB_PATH)

    table_name = "ab_results"
    if table_name not in db.table_names():
        console.print(f"[cyan]Creating new table '{table_name}' for A/B results...[/]")
        db[table_name].create(
            {"filename": str, "preference": str, "notes": str}, pk="filename"
        )
        db[table_name].create_index(["preference"])
        initialize_ab_db_with_choices(db)
    else:
        update_ab_db_with_new_choices(db)

    return db


def initialize_ab_db_with_choices(db: Database):
    """Initialize the ab_results table with all existing choices."""
    try:
        choices_data = load_choices()
        rows = [
            {
                "filename": choice.output.name,
                "preference": Preference.PENDING,
                "notes": None,
            }
            for choice in choices_data.choices
            if choice.output
        ]
        if rows:
            db["ab_results"].insert_all(rows, pk="filename", ignore=True)
            console.print(f"[green]Initialized A/B results table with {len(rows)} choices[/]")
    except Exception as e:
        console.print(f"[red]Error initializing A/B database: {e}[/]")


def update_ab_db_with_new_choices(db: Database):
    """Update the ab_results table with any new choices not already present."""
    try:
        choices_data = load_choices()
        existing_filenames = set(row["filename"] for row in db["ab_results"].rows)
        new_rows = [
            {
                "filename": choice.output.name,
                "preference": Preference.PENDING,
                "notes": None,
            }
            for choice in choices_data.choices
            if choice.output and choice.output.name not in existing_filenames
        ]
        if new_rows:
            db["ab_results"].insert_all(new_rows, pk="filename")
            console.print(f"[green]Added {len(new_rows)} new choices to the A/B results table[/]")
    except Exception as e:
        console.print(f"[red]Error updating A/B database with new choices: {e}[/]")


def save_ab_result(db: Database, filename: str, preference: Preference, notes: str | None = None):
    """Save the A/B test preference to the database."""
    db["ab_results"].upsert(
        {"filename": filename, "preference": preference, "notes": notes}, pk="filename"
    )


def get_ab_preference(db: Database, filename: str) -> Preference:
    """Get the current A/B preference status for a filename."""
    row = db["ab_results"].get(filename)
    return Preference(row["preference"]) if row else Preference.PENDING


# --- Stats Display ---


def display_ab_progress(db: Database):
    """Display the current A/B testing progress."""
    status_counts = {
        row["preference"]: row["count"]
        for row in db.query(
            "SELECT preference, COUNT(*) as count FROM ab_results GROUP BY preference"
        )
    }
    total = sum(status_counts.values())

    if total == 0:
        console.print("[yellow]No A/B results found in the database yet.[/]")
        return

    pref_a = status_counts.get(Preference.SET_A, 0)
    pref_b = status_counts.get(Preference.SET_B, 0)
    rejected = status_counts.get(Preference.REJECT, 0)
    pending = status_counts.get(Preference.PENDING, 0)

    table = Table(title="A/B Test Progress")
    table.add_column("Preference", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Percentage", style="green")

    table.add_row("Prefer A", str(pref_a), f"{pref_a / total * 100:.2f}%" if total else "0%")
    table.add_row("Prefer B", str(pref_b), f"{pref_b / total * 100:.2f}%" if total else "0%")
    table.add_row("Reject Both", str(rejected), f"{rejected / total * 100:.2f}%" if total else "0%")
    table.add_row("Pending", str(pending), f"{pending / total * 100:.2f}%" if total else "0%")
    table.add_row("Total", str(total), "100%")

    console.print(table)


# --- Command Handling ---


def play_pair(audio_path_1: Path, audio_path_2: Path):
    """Clear playlist and play the pair of audio files back-to-back."""
    sound_player.clear()
    console.print("[cyan]Playing audio 1...[/]")
    sound_player.queue(audio_path_1)
    # Need a slight delay or a way to know when first finishes before announcing second?
    # For now, let SoundPlayer handle queuing. User knows 1 plays then 2.
    sound_player.queue(audio_path_2)


def handle_ab_command(
    cmd: str,
    db: Database,
    filename: str,
    audio_1: Path,
    audio_2: Path,
    mapping: dict[int, str], # {1: 'A', 2: 'B'} or {1: 'B', 2: 'A'}
) -> bool:
    """
    Handle a command from user input during A/B testing.
    Returns True if the command loop should continue for this item, False if it should move to the next.
    """
    match cmd:
        case "1":
            chosen_set = mapping[1]
            save_ab_result(db, filename, Preference(chosen_set))
            console.print(f"[green]Marked as PREFER {chosen_set}[/]")
            return False # Move to next item
        case "2":
            chosen_set = mapping[2]
            save_ab_result(db, filename, Preference(chosen_set))
            console.print(f"[green]Marked as PREFER {chosen_set}[/]")
            return False # Move to next item
        case "r":
            save_ab_result(db, filename, Preference.REJECT)
            console.print("[red]Marked as REJECT BOTH[/]")
            return False # Move to next item
        case "n":
            # Ensure it's marked pending if it wasn't already
            save_ab_result(db, filename, Preference.PENDING)
            console.print("[yellow]Skipped, marked as PENDING[/]")
            return False # Move to next item
        case "p":
            console.print("\n[cyan]Replaying pair (1 then 2)...[/]")
            play_pair(audio_1, audio_2)
            return True # Continue with this item
        case "q":
            console.print("[yellow]Quitting A/B test...[/]")
            sound_player.shutdown()
            display_ab_progress(db) # Show final stats before exiting
            raise typer.Exit()
        case readchar.key.BACKSPACE:
            sound_player.stop()
            sound_player.clear()
            console.print("[yellow]Playback stopped[/]")
            return True # Continue with this item
        case _:
            console.print("[red]Invalid action.[/]")
            return True # Continue with this item


def run_ab_command_loop(
    db: Database,
    filename: str,
    audio_1: Path,
    audio_2: Path,
    mapping: dict[int, str]
):
    """Run the command loop for a single A/B test item."""
    console.print("\n[bold]Available actions:[/]")
    console.print("[cyan]1[/]: prefer audio 1  [cyan]2[/]: prefer audio 2  [cyan]r[/]: reject both")
    console.print("[cyan]n[/]: next (skip)     [cyan]p[/]: replay pair")
    console.print("[cyan]q[/]: quit            [cyan]backspace[/]: stop playback")

    while True:
        try:
            console.print("\nChoose preference or action: ", end="")
            action = readchar.readkey()
            console.print(action) # Echo the key pressed

            should_continue = handle_ab_command(action, db, filename, audio_1, audio_2, mapping)
            if not should_continue:
                return # Move to the next choice in the main loop
        except KeyboardInterrupt:
            console.print("[yellow]\nQuitting A/B test...[/]")
            sound_player.shutdown()
            display_ab_progress(db) # Show final stats
            raise typer.Exit()


# --- Main Application ---

@app.command("abtest")
def run_ab_test(
    dir_a: Path = typer.Argument(..., help="Directory containing the first set (A) of voice files.", exists=True, file_okay=False, readable=True),
    dir_b: Path = typer.Argument(..., help="Directory containing the second set (B) of voice files.", exists=True, file_okay=False, readable=True),
    start_index: int = typer.Option(0, "--start", "-s", help="Starting index for testing"),
    limit: int = typer.Option(None, "--limit", "-l", help="Limit the number of choices to test"),
    pending_only: bool = typer.Option(False, "--pending", "-p", help="Only show pending choices"),
):
    """
    Interactive CLI for A/B testing two sets of generated voice files.
    """
    # Initialize sound player thread
    sound_player.start()

    try:
        db = setup_ab_db()
        choices_data = load_choices()

        display_ab_progress(db)

        # Filter choices
        all_choices = [c for c in choices_data.choices if c.output] # Only choices with expected output
        if pending_only:
            filtered_choices = [
                choice for choice in all_choices
                if get_ab_preference(db, choice.output.name) == Preference.PENDING
            ]
            working_choices = filtered_choices
        else:
            working_choices = all_choices

        # Apply start index and limit
        if limit:
            working_choices = working_choices[start_index : start_index + limit]
        else:
            working_choices = working_choices[start_index:]

        if not working_choices:
            console.print("[yellow]No choices to test based on your filters.[/]")
            return

        console.print(f"[green]Loaded {len(working_choices)} choices for A/B testing.[/]")

        # A/B Test Loop
        for i, choice in enumerate(working_choices):
            filename = choice.output.name
            current_pref = get_ab_preference(db, filename)

            console.print(
                f"\n[bold cyan]Testing Choice {i + start_index + 1}/{len(working_choices)} - Current preference: {current_pref}[/]"
            )
            console.print(f"[dim]File: {filename}[/]")

            # Construct paths and check existence
            path_a = dir_a / filename
            path_b = dir_b / filename

            if not path_a.exists():
                console.print(f"[red]Audio file missing in Dir A: {path_a}[/]")
                console.print("[yellow]Skipping this choice.[/]")
                continue
            if not path_b.exists():
                console.print(f"[red]Audio file missing in Dir B: {path_b}[/]")
                console.print("[yellow]Skipping this choice.[/]")
                continue

            # Show context
            print_choice_context(choice)

            # Randomize A/B order
            sets = [('A', path_a), ('B', path_b)]
            random.shuffle(sets)
            set_1, audio_1 = sets[0]
            set_2, audio_2 = sets[1]
            mapping = {1: set_1, 2: set_2} # Track which original set is 1 and 2

            console.print(f"\n[cyan]Playing pair (Audio 1 then Audio 2)...[/]")
            play_pair(audio_1, audio_2)

            # Run command loop for this choice
            run_ab_command_loop(db, filename, audio_1, audio_2, mapping)

        # Final progress report
        console.print("\n[bold green]A/B testing session completed![/]")
        display_ab_progress(db)

    finally:
        # Ensure player is shut down
        sound_player.shutdown()


if __name__ == "__main__":
    app() 
