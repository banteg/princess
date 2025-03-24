import re
from functools import cache
from pathlib import Path

import rich
import typer
from pydantic import BaseModel

from princess.game import walk_script_files

app = typer.Typer()


CHARACTER_RE = re.compile(r'^define (?P<id>.*?) = Character\(_?\(?"(?P<name>[^"]*)"\)?')


class Character(BaseModel):
    id: str
    name: str

    def __str__(self):
        if self.name not in ["", "???"]:
            return self.name
        return self.id


@cache
def extract_characters(game_path=None):
    def extract_inner():
        for path in walk_script_files(game_path):
            for line in Path(path).read_text().splitlines():
                if match := CHARACTER_RE.search(line.lstrip()):
                    yield Character(**match.groupdict())

    return {c.id: c for c in extract_inner()}


@app.command("characters")
def print_characters():
    characters = extract_characters()
    rich.print(characters)
    for c in characters:
        print(c, characters[c], sep=" - ")

    print(f"\nextracted {len(characters)} characters")


if __name__ == "__main__":
    app()
