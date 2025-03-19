import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Lark, Transformer, v_args

from princess.constants import CHARACTERS
from princess.utils.dialogue import clean_choice_for_tts


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


@dataclass
class Text:
    line: int
    text: str


class ChoicesTransformer(Transformer):
    """
    Extract choices along with relevant dialogue surrounding them.
    """

    def __init__(self):
        self.labels: dict[int, str] = {}
        self.dialogue_buffer: list[Dialogue] = []
        self.choices: list[Choice] = []
        self.dialogue_stack: list[list[Dialogue]] = []

    @v_args(meta=True)
    def identifier(self, meta, items):
        return Text(line=meta.line, text=items[0].value)

    def condition(self, items):
        return items[0].value.strip()

    @v_args(meta=True)
    def quoted(self, meta, items):
        return Text(line=meta.line, text=items[0].value)

    def voice(self, items):
        return items[0].text

    def dialogue(self, items):
        character, text_token = items[:2]
        dlg = Dialogue(
            line=character.line,
            character=character.text,
            text=text_token.text,
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

    @v_args(meta=True)
    def label(self, meta, items):
        label_name = items[0]
        statements = items[1:]

        self.labels[meta.line] = label_name.text
        self.dialogue_buffer = []

        return {"label": label_name.text, "statements": statements}

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
            label=None,  # will be filled in start
            choice=choice_token.text,
            condition=condition,
            prev_dialogue=old_buffer.copy(),
            next_dialogue=next_dialogue,
        )
        self.choices.append(choice)

        return choice

    def find_label_at_line(self, line):
        keys = sorted(self.labels.keys())
        index = bisect_right(keys, line) - 1
        return self.labels[keys[index]]

    def start(self, items):
        for choice in self.choices:
            choice.label = self.find_label_at_line(choice.line)
        return self.choices


def show_choices(choices: list[Choice]):
    for enum, choice in enumerate(choices, 1):
        rich.print(f"[bold yellow]Choice {enum}:")
        for line in choice.prev_dialogue[-3:]:
            rich.print(f"[dim]\[{line.line}][/dim] [blue]{line.character}:[/] {line.text}")

        rich.print(f"[dim]\[{choice.line}][/dim] [green]choice:[/] {choice.choice}")
        pad = " " * (len(str(choice.line)) + 2)
        rich.print(
            f"{pad} [red]voiced:[/] {clean_choice_for_tts(choice.choice) or '[dim](silent)[/]'}"
        )

        for line in choice.next_dialogue[:3]:
            rich.print(f"[dim]\[{line.line}][/dim] [blue]{line.character}:[/] {line.text}")
        rich.print("\n")


def parse_script(path: Path, debug: bool = False):
    script = clean_script(path)
    result = grammar.parse(script)
    transformed = ChoicesTransformer().transform(result)
    if debug:
        rich.print(transformed)
        rich.print(len(transformed), "choices extracted")
        rich.print("\n")
        show_choices(transformed)
    return transformed


if __name__ == "__main__":
    typer.run(parse_script)
