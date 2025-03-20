"""
This pipeline extracts player choices and surrounding dialogue from the branching game scripts.

It consists of several stages:
1. Clean: preprocess the script to only keep the lines we are interested in.
2. Parse: use a minimal Lark grammar to parse the script into a tree structure (bottom-up).
3. Extract: traverse the tree top-down to extract the player choices and surrounding dialogue.
"""

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


@_app.command("clean")
def clean_script(path: Path, debug: bool = False):
    """
    Preprocess a script and only keep the lines we are interested in and our parser can handle.
    This version removes if/elif/else lines and dedents their bodies as if the conditions weren't there.
    """
    character_re = re.compile(r"^\s*(" + "|".join(CHARACTERS) + r")\s+\"")
    lines = Path(path).read_text().splitlines()

    def clean_inner():
        # stack holds tuples of (block_indent, removal_amount)
        stack = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Determine the current line's indent (number of leading spaces)
            indent_match = re.match(r"^(\s*)", line)
            current_indent = len(indent_match.group(1)) if indent_match else 0

            # Pop out of any control block when the current line is no longer as indented.
            while stack and current_indent <= stack[-1][0]:
                stack.pop()

            # Check if the line is an if/elif/else statement (a control line)
            if re.match(r"^\s*(if|elif|else)\b.*:\s*$", line):
                # Look ahead to the next non-empty line to determine the removal indent.
                removal = 0
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if next_line.strip() == "":
                        j += 1
                        continue
                    next_indent_match = re.match(r"^(\s*)", next_line)
                    next_indent = len(next_indent_match.group(1)) if next_indent_match else 0
                    if next_indent > current_indent:
                        removal = next_indent - current_indent
                    break
                if removal > 0:
                    stack.append((current_indent, removal))
                # Do not yield the if/elif/else line; skip it.
                i += 1
                continue
            else:
                # Compute total removal amount from all active control blocks.
                total_removal = sum(rem for _, rem in stack)
                # Remove the computed indentation from the line.
                if line.startswith(" " * total_removal):
                    new_line = line[total_removal:]
                else:
                    new_line = line.lstrip()
                # Only yield lines that are part of the "interesting" parts of the script.
                if (
                    re.search(r"^\s*label\s[a-z][a-z0-9_]*:", new_line)
                    or re.search(r"^\s*menu:", new_line)
                    or re.search(r'^\s*"(\{i\})?•', new_line)
                    or re.search(r'^\s*voice\s"[^"]+"', new_line)
                    or character_re.search(new_line)
                ):
                    yield new_line
            i += 1

    # The final newline is crucial.
    script = "\n".join(clean_inner()) + "\n"
    if debug:
        Path("clean_script.rpy").write_text(script)
    return script


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

    identifier: /[a-zA-Z_]\w*/  # python identifier
    quoted: "\"" /[^\"]+/ "\""  # quoted string
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
        choice, *rest = items
        condition = None
        next_dialogue = []
        if rest and isinstance(rest[0], str):
            condition = rest[0]
            rest = rest[1:]
        if rest:
            next_dialogue = list(self.extract_next_dialogue(rest))

        choice = Choice(
            line=choice.line,
            choice=choice.text,
            condition=condition,
            next_dialogue=next_dialogue,
        )
        return choice

    def extract_next_dialogue(self, items):
        """
        Extract dialogues that follow a choice up to next menu.
        """
        for item in items:
            if isinstance(item, Dialogue):
                yield item
            elif isinstance(item, Menu):
                break
            elif item.data == "label":
                yield from self.extract_next_dialogue(item.children[1:])
            elif item.data == "block":
                yield from self.extract_next_dialogue(item.children)

    def _find_context_at_line(self, items: list[Line], line: int):
        items = sorted(items, key=attrgetter("line"))
        lines = [item.line for item in items]
        index = bisect_right(lines, line) - 1
        return items[index] if index != -1 else Line(line=1)

    def find_label_at_line(self, line) -> Label:
        return self._find_context_at_line(self.labels, line)

    def find_menu_before_line(self, line) -> Menu:
        return self._find_context_at_line(self.menus, line - 1)

    def find_prev_dialogue(self, start, stop) -> list[Dialogue]:
        """
        Find dialogues between last label and menu start.
        """
        dialogues = [d for d in self.dialogues if d.line > start and d.line < stop]
        return dialogues

    def start(self, items):
        """
        After the whole tree has been transformed, we have all the labels, menus, and dialogue lines.
        Now we traverse it again to add labels and previous dialogue to choices before returning them.
        """
        choices = []
        for menu in self.menus:
            for choice in menu.choices:
                label = self.find_label_at_line(choice.line)
                prev_menu = self.find_menu_before_line(menu.line)
                choice.label = label.label
                choice.prev_menu = prev_menu
                choice.prev_dialogue = self.find_prev_dialogue(prev_menu.line, menu.line)
                choices.append(choice)

        return sorted(choices, key=attrgetter("line"))


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


@_app.command("parse")
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
