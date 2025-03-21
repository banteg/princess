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
    Preprocess a script and keep only the lines we are interested in (labels, menus, dialogue,
    if/elif/else blocks, jumps, etc.), preserving their indentation so our grammar can parse them.
    """
    character_re = re.compile(r"^\s*(" + "|".join(CHARACTERS) + r")\s+\"")

    # This regex tries to capture the typical Ren'Py lines we need:
    keep_re = re.compile(
        r""" ^
        (\s*
            (
                label\s+[a-z][a-z0-9_]*:  # label start
                |menu\s*:\s*              # choice menu
                |(if|elif|else)\b.*:\s*   # conditional blocks
                |jump\s+\w+               # jump label
                |voice\s+"[^"]+"          # voice "some_file"
                |"(\{i\})?•              # choice bullet
            )
        )
        """,
        re.VERBOSE | re.IGNORECASE,
    )
    if_re = re.compile(r"^(\s*)(if|elif|else)\b(.*):")
    # "{i}• Choice{/i}" [if condition]:
    choice_re = re.compile(r'(^\s*"\{i\}•[^"]+")(\s+if\b[^:]+)?:')
    # n "Dialogue\n" [id ch1_razor_alt_start_bb9f7415]
    dialogue_re = re.compile(r'(\s*)(\w+) ("[^"]+")( id .*)?')

    lines = Path(path).read_text().splitlines()

    def indent_of(line):
        return len(line) - len(line.lstrip())

    # Now we simply yield the lines that match `keep_re` or `character_re`
    # (the latter was for lines like:  n "some dialogue")
    def select_lines(lines):
        for line in lines:
            if keep_re.search(line) or character_re.search(line):
                if choice_re.search(line):
                    yield choice_re.sub(r"\1:", line)
                else:
                    yield line

    def fix_conditionals(lines):
        # make sure we don't have empty conditional blocks
        for i, line in enumerate(lines):
            if if_re.search(line):
                next_line = lines[i + 1]
                if indent_of(next_line) > indent_of(line):
                    yield if_re.sub(r"\1\2:", line)
            elif dialogue_re.search(line):
                yield dialogue_re.sub(r"\1\2 \3", line)
            else:
                yield line

    lines = list(select_lines(lines))
    lines = list(fix_conditionals(lines))
    script = "\n".join(lines) + "\n"
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
    start: statement* _NL?

    ?statement: label
              | menu
              | voiced_dialogue
              | dialogue
              | voice
              | if_block
              | jump
              | pass

    # Modified conditionals to handle empty blocks
    if_block: "if" ":" _NL block (elif_block)* (else_block)?
    elif_block: "elif" ":" _NL block
    else_block: "else" ":" _NL block

    condition: /[^\n:]+/
    jump: "jump" identifier _NL
    pass: "pass" _NL

    block: _INDENT statement+ _DEDENT

    label: "label" identifier ":" _NL [block]
    menu: "menu" ":" _NL _INDENT choice+ _DEDENT
    choice: quoted condition? ":" _NL [block]

    voiced_dialogue: voice _NL dialogue
    dialogue: identifier quoted _NL
    voice: "voice" quoted

    identifier: /[a-zA-Z_]\w*/  # python identifier
    quoted: "\"" /[^\"]+/ "\""  # quoted string

    _NL: /\r?\n[\t ]*/  # MUST match line break as well as indentation
    %declare _INDENT _DEDENT
    %import common.WS_INLINE
    %ignore WS_INLINE
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
