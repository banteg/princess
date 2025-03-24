import rich
import typer

from princess.choices import ChoiceResultList, extract_choices
from princess.game import walk_script_files
from princess.parser import parse_script
from pathlib import Path
import pickle
app = typer.Typer()


@app.command("run")
def run_pipeline():
    result = ChoiceResultList(choices=[])
    for path in walk_script_files():
        script = parse_script(path)
        result.choices.extend(extract_choices(script, script_path=path))

    rich.print(len(result.choices))
    Path("output/choices.json").write_text(result.model_dump_json(indent=2))
    Path("output/choices.pickle").write_bytes(pickle.dumps(result))

if __name__ == "__main__":
    app()
