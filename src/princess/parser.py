"""
This pipeline extracts player choices and surrounding dialogue from the branching game scripts.

It consists of several stages:
1. Clean: preprocess the script to only keep the lines we are interested in.
2. Parse: use a minimal Lark grammar to parse the script into a tree structure (bottom-up).
3. Extract: traverse the tree top-down to extract the player choices and surrounding dialogue.
"""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Discard, Lark, Token, Transformer, Tree, v_args
from lark.indenter import Indenter

from princess.game import get_game_path, walk_script_files

_app = typer.Typer(pretty_exceptions_show_locals=False)

"""
Stage 1: Indentation parser
Construct a raw tree from indented structure for further processing.
"""

label_re = re.compile(r"^\s*label [a-z]\w*:$")
menu_re = re.compile(r"^\s*menu:$")
jump_re = re.compile(r"^\s*jump \w+$")
voice_re = re.compile(r"^\s*voice \"[^\"]+\"$")
dialogue_re = re.compile(r'^\s*\w+ "[^"]+"( id .*)?$')
choice_re = re.compile(r'^\s*"(\{i\})?•[^"]+"( if .+)?:')
condition_re = re.compile(r"^\s*(if|elif|else).*:")


@dataclass
class Meta:
    line: int
    indent: int


def is_empty(line: str) -> bool:
    return not line.strip() or line.strip().startswith("#")


def is_block_start(line: str) -> bool:
    return line.rstrip().endswith(":")


def line_token(line: str) -> str:
    if label_re.search(line):
        return "LABEL"
    elif menu_re.search(line):
        return "MENU"
    elif jump_re.search(line):
        return "JUMP"
    elif voice_re.search(line):
        return "VOICE"
    elif dialogue_re.search(line):
        return "DIALOGUE"
    elif choice_re.search(line):
        return "CHOICE"
    elif condition_re.search(line):
        return "CONDITION"
    else:
        return "LINE"


def build_script_tree(script: str) -> Tree:
    """
    Parse an indented script into a tree structure.
    """
    assert isinstance(script, str)
    root = Tree("start", [], meta=Meta(line=0, indent=-1))
    stack = [root]
    lines = script.splitlines()
    for lineno, line in enumerate(lines, start=1):
        if is_empty(line):
            continue
        strip = line.strip()
        indent = len(line) - len(line.lstrip())
        meta = Meta(line=lineno, indent=indent)

        # we dedented so we pop all blocks that we exited
        while stack and indent <= stack[-1].meta.indent:
            stack.pop()

        if is_block_start(line):
            # add block[header, body]
            header = Token(line_token(line), strip, line=lineno)
            body = Tree("body", [], meta=meta)
            block = Tree("block", [header, body], meta=meta)
            # add block to parent, but put children in body
            stack[-1].children.append(block)
            stack.append(body)
        else:
            # append line to the parent body
            token = Token(line_token(line), strip, line=lineno)
            stack[-1].children.append(token)

    return root


"""
Stage 2: Cleanup
Remove lines that weren't assigned a token and blocks with no children.
"""


class CleanupTransformer(Transformer):
    def LINE(self, token):
        # strip lines that weren't assigned a token
        return Discard

    def block(self, children):
        header, body = children
        num_sub = len([sub for sub in body.children if sub])
        # strip empty subtrees
        if num_sub == 0:
            return Discard
        return Tree("block", children)


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
    voice: "voice" quoted _NL

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
