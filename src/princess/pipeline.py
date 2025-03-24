import rich
import typer

from princess.choices import ChoiceResult, ChoiceResultList, extract_choices
from princess.game import walk_script_files
from princess.parser import parse_script
from princess.voice import clean_choice_for_voice, get_output_path, generate_choice_audio
from pathlib import Path
import pickle

app = typer.Typer()


def filter_spoken_lines(source: ChoiceResultList) -> ChoiceResultList:
    clean_choices = ChoiceResultList()
    seen = set()
    for choice in source.choices:
        choice.clean = clean_choice_for_voice(choice.choice)
        if choice.clean and choice.clean not in seen:
            seen.add(choice.clean)
            choice.output = get_output_path(choice)
            clean_choices.choices.append(choice)

    return clean_choices


@app.command("run")
def run_pipeline():
    # extract raw choices
    raw_choices = ChoiceResultList(choices=[])
    for path in walk_script_files():
        script = parse_script(path)
        raw_choices.choices.extend(extract_choices(script, script_path=path))

    rich.print(f"extracted {len(raw_choices.choices)} choices")
    Path("output/raw_choices.json").write_text(raw_choices.model_dump_json(indent=2))
    Path("output/choices.pickle").write_bytes(pickle.dumps(raw_choices))

    # filter out spoken lines
    clean_choices = filter_spoken_lines(raw_choices)
    rich.print(f"narrowed down to {len(clean_choices.choices)} voice lines")
    Path("output/clean_choices.json").write_text(
        clean_choices.model_dump_json(indent=2)
    )

    # check existing audio files
    base = clean_choices.choices[0].output.parent
    existing_files = set(base.glob("*.flac"))
    expected_files = {choice.output for choice in clean_choices.choices}

    unexpected_files = existing_files - expected_files
    missing_files = expected_files - existing_files

    rich.print(f"found {len(existing_files)} existing files")
    rich.print(f"found {len(unexpected_files)} unexpected files")
    for file in unexpected_files:
        rich.print(f"    {file}")
    if unexpected_files and typer.confirm("delete unexpected files?"):
        for file in unexpected_files:
            file.unlink()

    rich.print(f"found {len(missing_files)} missing files")
    missing_choices = {choice.output: choice for choice in clean_choices.choices}
    for file in missing_files:
        rich.print(f"[dim]{file}")
        rich.print(missing_choices[file].clean)

    if missing_choices and typer.confirm("generate missing files?"):
        for choice in missing_choices.values():
            generate_choice_audio(choice)


if __name__ == "__main__":
    app()
