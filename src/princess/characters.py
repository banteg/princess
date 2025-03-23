import re
from pathlib import Path

import rich
import typer

from princess.game import walk_script_files

app = typer.Typer()


def extract_characters(game_path=None):
    CHARACTER_RE = re.compile(r"^define (.*?) = Character\(")

    def extract_inner():
        for path in walk_script_files(game_path):
            for line in Path(path).read_text().splitlines():
                if match := CHARACTER_RE.search(line.lstrip()):
                    yield match.group(1)

    return list(extract_inner())


@app.command("characters")
def print_characters():
    characters = extract_characters()
    rich.print(characters)


if __name__ == "__main__":
    app()
