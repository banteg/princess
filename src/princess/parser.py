from operator import attrgetter
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Lark, Transformer, v_args, Tree
from lark.indenter import Indenter
import sys

from princess.constants import CHARACTERS
from princess.utils.dialogue import clean_choice_for_tts

_app = typer.Typer(pretty_exceptions_show_locals=False)


def clean_script(path):
    """
    Preprocess a script and only keep the lines we are interested in and our parser can handle.
    """
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

    # the final newline is crucial
    return "\n".join(clean_inner()) + "\n"


class RenpyIndenter(Indenter):
    """
    Postlexer to inject _INDENT/_DEDENT tokens based on indentation.
    """

    NL_type = "_NL"
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


grammar = Lark(
    r"""
    %import common.WS_INLINE
    %ignore WS_INLINE

    _NL: /\r?\n[\t ]*/  # MUST match line break as well as indentation
    %declare _INDENT _DEDENT

    start: statement*
    ?statement: label | menu | voiced_dialogue | dialogue

    block: _INDENT statement* _DEDENT

    label: "label" identifier ":" _NL block?
    menu: "menu" ":" _NL _INDENT choice+ _DEDENT
    choice: quoted condition? ":" _NL block?

    voiced_dialogue: voice _NL dialogue
    dialogue: identifier quoted ["id" identifier] _NL
    voice: "voice" quoted
    condition: "if" /[^\n:]+/    # if statement

    ?identifier: /[a-zA-Z_]\w*/  # python identifier
    ?quoted: "\"" /[^\"]+/ "\""  # quoted string
    """,
    parser="lalr",
    postlex=RenpyIndenter(),
    propagate_positions=True,
)


@dataclass
class Line:
    line: int


@dataclass
class Dialogue(Line):
    character: str
    text: str
    voice: str | None = None


@dataclass
class Choice(Line):
    choice: str
    condition: str
    label: str | None = None
    prev_dialogue: list[Dialogue] | None = None
    next_dialogue: list[Dialogue] | None = None


@dataclass
class Menu(Line):
    choices: list[Choice]


@dataclass
class Label(Line):
    label: str


@dataclass
class Text(Line):
    text: str


@dataclass
class Block(Line):
    statements: list[Line]


class ChoicesTransformer(Transformer):
    """
    Extract choices along with relevant dialogue surrounding them.
    """

    def __init__(self):
        self.labels: list[Label] = []
        self.dialogues: list[Dialogue] = []
        self.menus: list[Menu] = []

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
        return dlg

    def _filter_dialogue(self, dlg: Dialogue):
        if re.search(r"^Note:", dlg.text) or "{fast}" in dlg.text:
            return False
        return True

    def voiced_dialogue(self, items):
        voice_path, dialogue = items
        dialogue.voice = voice_path
        if self._filter_dialogue(dialogue):
            self.dialogues.append(dialogue)
        return dialogue

    @v_args(meta=True)
    def label(self, meta, items):
        label_name = items[0]
        label = Label(line=label_name.line, label=label_name.text)
        self.labels.append(label)
        return Tree("label", items)

    @v_args(meta=True)
    def menu(self, meta, items):
        menu = Menu(line=meta.line, choices=items)
        self.menus.append(menu)
        return Tree("menu", items)

    def choice(self, items):
        rich.print("---- CHOICE ----", items, "end choice")
        return Tree("choice", items)

    # def choice(self, items):
    #     rich.print("choice", items, "end choice")
    #     choice_token = items[0]
    #     condition = None
    #     idx = 1
    #     if len(items) > 1 and isinstance(items[1], str):
    #         condition = items[1]
    #         idx += 1
    #     next_dialogue = []
    #     rich.print(items[idx:])
    #     if len(items) > idx:
    #         for stmt in items[idx:]:
    #             if isinstance(stmt, Dialogue):
    #                 next_dialogue.append(stmt)
    #     choice = Choice(
    #         line=choice_token.line,
    #         choice=choice_token.text,
    #         condition=condition,
    #     )
    #     return choice

    # def _find_context_at_line(self, items: list[Line], line: int):
    #     items = sorted(items, key=attrgetter("line"))
    #     lines = [item.line for item in items]
    #     index = bisect_right(lines, line) - 1
    #     return items[index] if index != -1 else Line(line=1)

    # def find_label_at_line(self, line) -> Label:
    #     return self._find_context_at_line(self.labels, line)

    # def find_menu_before_line(self, line) -> Menu:
    #     return self._find_context_at_line(self.menus, line - 1)

    # def find_prev_dialogue(self, start, stop) -> list[Dialogue]:
    #     """
    #     Find dialogues between last label and menu start.
    #     """
    #     rich.print(f"find dialogue between {start} and {stop}")
    #     dialogues = [d for d in self.dialogues if d.line > start and d.line < stop]
    #     return dialogues

    # def start(self, items):
    #     """
    #     After the whole tree has been transformed, we have all the labels, menus, and dialogue lines.
    #     Now we traverse it again to add labels and previous dialogue to choices before returning them.
    #     """
    #     choices = []
    #     for menu in self.menus:
    #         for choice in menu.choices:
    #             label = self.find_label_at_line(choice.line)
    #             prev_menu = self.find_menu_before_line(menu.line)
    #             choice.label = label.label
    #             choice.prev_menu = prev_menu
    #             choice.prev_dialogue = self.find_prev_dialogue(prev_menu.line, menu.line)
    #             choices.append(choice)
    #     rich.print("labels")
    #     rich.print(self.labels)
    #     rich.print("menus")
    #     rich.print(self.menus)
    #     rich.print("dialogue_lines")
    #     rich.print(self.dialogues)
    #     return choices


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


@_app.command()
def parse_script(path: Path, debug: bool = False):
    print("=" * 120)
    script = clean_script(path)
    result = grammar.parse(script)
    rich.print(result)
    transformed = ChoicesTransformer().transform(result)
    if debug:
        rich.print(transformed)
        rich.print(len(transformed), "choices extracted")
        rich.print("\n")
        show_choices(transformed)
    return transformed


if __name__ == "__main__":
    _app()
