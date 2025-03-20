"""
This pipeline extracts player choices and surrounding dialogue from the branching game scripts.

It consists of several stages:
1. Clean: preprocess the script to only keep the lines we are interested in.
2. Parse: use a minimal Lark grammar to parse the script into a tree structure (bottom-up).
3. Extract: traverse the tree top-down to extract the player choices and surrounding dialogue.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Discard, Lark, Transformer, v_args
from lark.indenter import Indenter
from princess.game import get_game_path, walk_script_files
from princess.constants import CHARACTERS
from collections import Counter

_app = typer.Typer(pretty_exceptions_show_locals=False)


# Stage 1: Clean
# Here we preprocess the script for our minimal grammar and only keep the lines we are interested in.
# We also dedent the bodies of control blocks as if the conditions weren't there.


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


# Stage 2: Parse
# Here we use a minimal Lark grammar to parse the script into a tree structure.
# Then we transform it into a tree infused with metadata like line numbers.
# We also merge voice and dialogue nodes into a unified node.


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
class Subtree:
    children: list


@dataclass
class Dialogue(Line):
    character: str
    dialogue: str
    voice: str | None = None


@dataclass
class Choice(Line, Subtree):
    choice: str


@dataclass
class Label(Line, Subtree):
    label: str


@dataclass
class Menu(Line, Subtree):
    children: list[Choice]


class RenpyTransformer(Transformer):
    def quoted(self, items):
        return items[0]

    def identifier(self, items):
        return items[0]

    @v_args(meta=True)
    def dialogue(self, meta, items):
        return Dialogue(
            character=items[0].value,
            dialogue=items[1].value,
            line=meta.line,
        )

    def voice(self, items):
        return items[0]

    def voiced_dialogue(self, items):
        dialogue = items[1]
        dialogue.voice = items[0].value
        return dialogue

    def condition(self, items):
        return Discard

    @v_args(meta=True)
    def choice(self, meta, items):
        return Choice(
            line=meta.line,
            choice=items[0].value,
            children=items[1] if len(items) > 1 else [],
        )

    @v_args(meta=True)
    def label(self, meta, items):
        return Label(
            line=meta.line,
            label=items[0].value,
            children=items[1] if len(items) > 1 else [],
        )

    @v_args(meta=True)
    def menu(self, meta, items):
        return Menu(line=meta.line, children=items)

    def block(self, items):
        return items

    def start(self, items):
        return Subtree(children=items)


# Stage 3: Extract choices
# Here we extract choices and their surrounding dialogue by traversing the tree.
# The resulting list can be used for further work on text-to-speech generation.


@dataclass
class ChoiceResult(Line):
    choice: str
    previous: list[Dialogue]
    subsequent: list[Dialogue]
    label: str | None = None


def extract_choices(tree) -> list[ChoiceResult]:
    def collect_until_menu(node):
        for sub in node.children:
            match sub:
                case Dialogue():
                    yield sub
                case Label():
                    yield from collect_until_menu(sub)
                case Menu():
                    return

    def walk_tree(node, prev=None, label=None):
        if prev is None:
            prev = []
        for sub in node.children:
            match sub:
                case Dialogue():
                    prev.append(sub)
                case Label():
                    label = sub.label
                    yield from walk_tree(sub, prev[:], label)
                case Menu():
                    yield from walk_tree(sub, prev[:], label)
                case Choice():
                    succ = list(collect_until_menu(sub))
                    yield ChoiceResult(
                        line=sub.line,
                        choice=sub.choice,
                        previous=prev[:],
                        subsequent=succ,
                        label=label,
                    )
                    post_prev = prev[:] + [Choice(line=sub.line, choice=sub.choice, children=[])]
                    yield from walk_tree(sub, post_prev, label)

    return list(walk_tree(tree))


@_app.command("parse")
def parse_script(path: Path, debug: bool = False):
    script = clean_script(path)
    raw_tree = grammar.parse(script)
    ast_tree = RenpyTransformer().transform(raw_tree)
    if debug:
        rich.print(ast_tree)
    return ast_tree


@_app.command("choices")
def extract_choices_from_script(path: Path, debug: bool = False):
    ast_tree = parse_script(path, debug)
    choices = extract_choices(ast_tree)
    if debug:
        rich.print(choices)
        rich.print(f"Extracted {len(choices)} choices")
    return choices


@_app.command("all")
def extract_all_choices(debug: bool = False):
    all_choices = []
    stats = Counter()
    game_path = get_game_path()
    for path in walk_script_files(game_path):
        print(path)
        try:
            ast_tree = parse_script(path)
            choices = extract_choices(ast_tree)
            if debug:
                rich.print(f"Extracted {len(choices)} choices from {path.relative_to(game_path)}\n")
            all_choices.extend(choices)
            stats["success"] += 1
        except Exception as e:
            print(f"Error parsing {path.relative_to(game_path)}: {e}\n")
            stats["errors"] += 1
    if debug:
        rich.print(f"Extracted {len(all_choices)} choices from all scripts")
        rich.print(stats, sum(stats.values()))
    return all_choices


if __name__ == "__main__":
    _app()
