import re
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Lark, Transformer

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
    start: statement+
    ?statement: label | menu | voiced_dialogue | dialogue

    label: "label" identifier ":" statement+
    menu: "menu:" choice+
    choice: quoted condition? ":" statement*
    voiced_dialogue: voice dialogue

    condition: "if" /[^\n:]+/
    voice: "voice" quoted
    dialogue: identifier quoted id?

    id: "id" identifier
    identifier: /[a-zA-Z_]\w*/
    quoted: "\"" /[^\"]+/ "\""

    %import common.WS
    %ignore WS
""",
    propagate_positions=True,
)


@dataclass
class Dialogue:
    line: int
    character: str
    text: str
    voice: str | None = None


@dataclass
class Choice:
    line: int
    label: str | None
    choice: str
    condition: str | None
    prev_dialogue: list[Dialogue]
    next_dialogue: list[Dialogue]


class ChoicesTransformer(Transformer):
    """
    Extract choices along with relevant dialogue surrounding them.
    """

    def __init__(self):
        self.current_label: str | None = None
        self.dialogue_buffer: list[Dialogue] = []
        self.choices: list[Choice] = []
        self.dialogue_stack: list[list[Dialogue]] = []

    def identifier(self, items):
        return items[0].value

    def condition(self, items):
        return items[0].value.strip()

    def quoted(self, items):
        return items[0]

    def voice(self, items):
        return items[0].value

    def dialogue(self, items):
        character, text_token = items[:2]
        dlg = Dialogue(
            line=text_token.line,
            character=character,
            text=text_token.value,
        )
        if self._filter_dialogue(dlg):
            self.dialogue_buffer.append(dlg)
        return dlg

    def _filter_dialogue(self, dlg: Dialogue):
        if re.search(r"^Note:", dlg.text) or "{fast}" in dlg.text:
            return False
        return True

    def voiced_dialogue(self, items):
        voice_path, dialogue = items
        dialogue.voice = voice_path
        # self.dialogue_buffer.append(dialogue)  # ONLY append here!
        return dialogue

    def label(self, items):
        label_name = items[0]
        statements = items[1:]

        self.current_label = label_name
        self.dialogue_buffer = []

        return {"label": label_name, "statements": statements}

    def menu(self, items):
        # Menu introduces choices; dialogue buffer holds dialogue before choices
        return {"menu": items}

    def choice(self, items):
        choice_token = items[0]
        condition = None
        statements = []
        idx = 1
        if len(items) > 1 and isinstance(items[1], str):
            condition = items[1]
            idx += 1
        statements = items[idx:]

        # Temporarily replace buffer for statements inside the choice
        old_buffer = self.dialogue_buffer
        self.dialogue_buffer = []

        next_dialogue = []
        for stmt in statements:
            if isinstance(stmt, Dialogue):
                next_dialogue.append(stmt)
            elif isinstance(stmt, dict) and "statements" in stmt:
                next_dialogue.extend([s for s in stmt["statements"] if isinstance(s, Dialogue)])

        self.dialogue_buffer = old_buffer

        choice = Choice(
            line=choice_token.line,
            label=self.current_label,
            choice=choice_token.value,
            condition=condition,
            prev_dialogue=old_buffer.copy(),
            next_dialogue=next_dialogue,
        )
        self.choices.append(choice)

        return choice

    def start(self, items):
        return self.choices


def parse_script(path: Path, debug: bool = False):
    script = clean_script(path)
    result = grammar.parse(script)
    transformed = ChoicesTransformer().transform(result)
    if debug:
        rich.print(transformed)
        rich.print(len(transformed), "choices extracted")
    return transformed


if __name__ == "__main__":
    typer.run(parse_script)
