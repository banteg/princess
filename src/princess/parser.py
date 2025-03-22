"""
RenPy script parsing pipeline. We don't use any grammar and instead work our way like this.
1. Indenter: Construct a tree from Python-like identation, assign known tokens.
2. Transformer: Remove lines that weren't assigned a token, remove empty blocks, merge voice and dialogue.
"""

import itertools
import re
from dataclasses import dataclass
from pathlib import Path

import rich
import typer
from lark import Discard, Token, Transformer, Tree

from princess.constants import CHARACTERS

app = typer.Typer(pretty_exceptions_show_locals=False)

"""
Stage 1: Indentation parser
Construct a raw tree from indented structure for further processing.
"""

label_re = re.compile(r"^\s*label (?P<label>\w+):$")
menu_re = re.compile(r"^\s*menu:$")
jump_re = re.compile(r"^\s*jump (?P<dest>\w+)$")
voice_re = re.compile(r"^\s*voice \"(?P<voice>[^\"]+)\"$")
dialogue_re = re.compile(
    r"^\s*(?P<character>" + "|".join(CHARACTERS) + r') "(?P<dialogue>[^"]+)"( id .*)?$'
)
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
Remove lines that weren't assigned a token, empty blocks. Merge voice and dialogue lines. Parse choices and labels.
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


def parse_script(path: Path) -> Tree:
    script = path.read_text()
    tree = build_script_tree(script)
    return DialogueTransformer().transform(tree)


@app.command("parse")
def parse_and_print(path: Path) -> Tree:
    tree = parse_script(path)
    rich.print(tree)


if __name__ == "__main__":
    app()
