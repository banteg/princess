import re
from pathlib import Path

import rich
from lark import Lark
import typer

from princess.constants import CHARACTERS


def clean_script(path):
    character_re = re.compile(r"^\s*(" + "|".join(CHARACTERS) + r")\s+\"")

    def clean_inner():
        for line in Path(path).read_text().splitlines():
            if re.search(r"^\s*label\s[a-z][a-z0-9_]*:", line):
                yield line
            elif re.search(r"^\s*menu:", line):
                yield line
            elif re.search(r'^\s*"(\{i\})?•', line):
                yield line
            elif re.search(r'^\s*voice\s"[^"]+"', line):
                yield line
            elif character_re.search(line):
                yield line

    return "\n".join(clean_inner())


grammar = Lark(
    r"""
    script: statement+
    ?statement: label | menu | voice | dialogue

    label: "label" identifier ":" statement+
    menu: "menu:" choice+
    choice: quoted condition? ":" statement*

    condition: "if" /[^\n:]+/
    voice: "voice" quoted
    dialogue: identifier quoted id?

    id: "id" identifier
    identifier: /[a-zA-Z_]\w*/
    quoted: "\"" /[^\"]+/ "\""

    %import common.WS
    %ignore WS
""",
    start="script",
)


def parse_script(path: Path):
    script = clean_script(path)
    result = grammar.parse(script)
    rich.print(result)
    return result


if __name__ == "__main__":
    typer.run(parse_script)
