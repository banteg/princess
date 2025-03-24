import pickle
from pathlib import Path

import rich
import typer
from rich.progress import track

from princess.choices import ChoiceResultList, extract_choices
from princess.game import walk_script_files
from princess.parser import parse_script
from princess.voice import generate_choice_audio

app = typer.Typer()


@app.command("run")
def run_pipeline():
    # extract spoken choices
    choices = ChoiceResultList()
    seen = set()
    for path in walk_script_files():
        script = parse_script(path)
        for choice in extract_choices(script, script_path=path):
            if choice.clean and choice.clean not in seen:
                seen.add(choice.clean)
                choices.choices.append(choice)

    rich.print(f"extracted {len(choices.choices)} spoken choices")
    Path("output/choices.pickle").write_bytes(pickle.dumps(choices))

    # check existing audio files
    base_dir = choices.choices[0].output.parent
    existing_files = set(base_dir.glob("*.flac"))
    expected_files = {choice.output for choice in choices.choices}

    unexpected_files = existing_files - expected_files
    missing_files = expected_files - existing_files

    rich.print(f"[green]found {len(existing_files)} existing files")
    rich.print(f"[yellow]found {len(missing_files)} missing files")
    rich.print(f"[red]found {len(unexpected_files)} unexpected files")

    for file in unexpected_files:
        rich.print(f"[red]{file}")
    if unexpected_files and typer.confirm("delete unexpected files?"):
        for file in unexpected_files:
            file.unlink()

    missing_choices = {choice.output: choice for choice in choices.choices}

    if missing_choices and typer.confirm("generate missing files?"):
        for choice in track(missing_choices.values()):
            generate_choice_audio(choice)


if __name__ == "__main__":
    app()
