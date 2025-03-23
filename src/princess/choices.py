"""
Stage 3: Extract choices
We extract choices and their surrounding dialogue by traversing the Script tree.
The resulting list can be used for text-to-speech generation.
"""

from dataclasses import dataclass
from pathlib import Path

import rich
import typer

from princess.parser import Choice, Condition, Dialogue, Jump, Label, Menu, Script, parse_script


@dataclass
class ChoiceResult:
    line: int
    choice: str
    condition: str | None
    label: str | None
    previous_dialogues: list[Dialogue]
    subsequent_dialogues: list[Dialogue]


def extract_choices(script: Script) -> list[ChoiceResult]:
    results: list[ChoiceResult] = []

    def walk(node, path: list[Dialogue | Choice], current_label: str | None):
        """
        'path' is a list of items (Dialogue, Choice, etc.) that led us here.
        'current_label' is the active label name.
        """

        match node:
            case Script() | Menu() | Condition():
                for child in node.children:
                    walk(child, path, current_label)

            case Label(label=new_label):
                for child in node.children:
                    walk(child, path, new_label)

            case Dialogue():
                path.append(node)

            case Choice(line=ln, choice=choice_text, condition=cond, children=cc):
                # Step A: gather subsequent dialogues from 'cc'
                subs = list(collect_dialogues_until_junction(cc))

                # Step B: build a ChoiceResult
                cr = ChoiceResult(
                    line=ln,
                    choice=choice_text,
                    condition=cond,
                    label=current_label,
                    previous_dialogues=path[:],
                    subsequent_dialogues=subs,
                )
                results.append(cr)

                # Step C: For nested blocks, we append the current choice to the path
                chosen = Choice(line=ln, choice=choice_text, condition=cond, children=[])
                new_path = path[:] + [chosen]

                # Now walk deeper (unless next is a junction)
                for child in cc:
                    walk(child, new_path, current_label)

    walk(script, [], None)
    return results


def collect_dialogues_until_junction(children: list) -> list[Dialogue]:
    for child in children:
        # 1) If child is a junction (Menu, Condition, Jump, etc.), STOP
        match child:
            case Menu() | Condition() | Jump():
                return
            case Dialogue():
                yield child
            case Label(children=subchildren):
                # Recurse further
                sub_found = collect_dialogues_until_junction(subchildren)
                yield from sub_found


def extract_choices_from_script(path: Path):
    script = parse_script(path)
    choices = extract_choices(script)
    rich.print(choices)
    return choices


if __name__ == "__main__":
    typer.run(extract_choices_from_script)
