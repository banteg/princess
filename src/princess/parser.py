"""
This pipeline extracts player choices and surrounding dialogue from the branching game scripts.

It consists of several stages:
1. Clean: preprocess the script to only keep the lines we are interested in.
2. Parse: use a minimal Lark grammar to parse the script into a tree structure (bottom-up).
3. Extract: traverse the tree top-down to extract the player choices and surrounding dialogue.
"""

import itertools
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Discard, Token, Transformer, Tree

from princess.game import get_game_path, walk_script_files

_app = typer.Typer(pretty_exceptions_show_locals=False)

"""
Stage 1: Indentation parser
Construct a raw tree from indented structure for further processing.
"""

label_re = re.compile(r"^\s*label (?P<label>\w+):$")
menu_re = re.compile(r"^\s*menu:$")
jump_re = re.compile(r"^\s*jump (?P<dest>\w+)$")
voice_re = re.compile(r"^\s*voice \"(?P<voice>[^\"]+)\"$")
dialogue_re = re.compile(r'^\s*(?P<character>\w+) "(?P<dialogue>[^"]+)"( id .*)?$')
choice_re = re.compile(r'^\s*"(?P<choice>(?:\{i\})?•[^"]+)"(?: if (?P<condition>.+))?:$')
condition_re = re.compile(r"^\s*(if|elif|else).*:$")


@dataclass
class Meta:
    line: int
    indent: int


def is_empty(line: str) -> bool:
    return not line.strip() or line.strip().startswith("#")


def is_block_start(line: str) -> bool:
    return line.rstrip().endswith(":")


def line_token(line: str, header: bool = False) -> str:
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
        return "HEADER" if header else "LINE"


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
            header = Token(line_token(line, header=True), strip, line=lineno)
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
Stage 2: Transform
Remove lines that weren't assigned a token, empty blocks.
Merge voice and dialogue lines.
Parse choices and labels.
"""


@dataclass
class Dialogue:
    line: int
    character: str
    dialogue: str
    voice: str | None = None


@dataclass
class Choice:
    choice: str
    condition: str | None = None


@dataclass
class Label:
    label: str


class DialogueTransformer(Transformer):
    def body(self, children):
        result = []
        skip = False
        for node, succ in itertools.pairwise(children):
            if skip:
                skip = False
                continue
            match node, succ:
                case Token("VOICE", voice_str), Token("DIALOGUE", dialogue_str):
                    voice_search = voice_re.search(voice_str)
                    dialogue_search = dialogue_re.search(dialogue_str)
                    result.append(
                        Dialogue(
                            line=succ.line,
                            **voice_search.groupdict(),
                            **dialogue_search.groupdict(),
                        )
                    )
                    skip = True
                case _:
                    result.append(node)
        if not skip and children:
            result.append(children[-1])
        return Tree("body", result)

    def block(self, children):
        header, body = children
        num_sub = len([sub for sub in body.children if sub])
        # strip empty subtrees
        if num_sub == 0:
            return Discard
        return Tree("block", children)

    def CHOICE(self, token):
        search = choice_re.search(token.value)
        return Choice(**search.groupdict())

    def LABEL(self, token):
        search = label_re.search(token.value)
        return Label(**search.groupdict())

    def LINE(self, token):
        # strip lines that weren't assigned a token
        return Discard


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
