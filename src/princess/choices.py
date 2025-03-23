# Stage 3: Extract choices
# Here we extract choices and their surrounding dialogue by traversing the tree.
# The resulting list can be used for text-to-speech generation.
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


def is_junction(node) -> bool:
    match node:
        case Menu() | Condition() | Jump():
            return True
        case _:
            return False


def extract_choices(script: Script) -> list[ChoiceResult]:
    results: list[ChoiceResult] = []

    def walk(node, path: list, current_label: str | None):
        """
        'path' is a list of items (Dialogue, Choice, etc.) that led us here.
        'current_label' is the active label name.
        """

        match node:
            # 1) Top-level script
            case Script(children=ch):
                for c in ch:
                    walk(c, path, current_label)

            # 2) Label
            case Label(line=ln, label=lbl, children=ch):
                # Recurse into children, preserving the path exactly,
                # so we don't double-append a line.
                for child in ch:
                    walk(child, path, lbl)

            # 3) Menu (just traverse children)
            case Menu(line=ln, children=ch):
                for child in ch:
                    walk(child, path, current_label)

            # 4) Condition (like if/elif/else)
            case Condition(line=ln, kind=k, condition=cond, children=ch):
                for child in ch:
                    walk(child, path, current_label)

            # 5) Dialogue => add to path
            case Dialogue():
                path.append(node)

            # 6) Choice => produce a ChoiceResult, then recurse with the choice in path
            case Choice(line=ln, choice=choice_text, condition=cond, children=cc):
                # Step A: gather subsequent dialogues from 'cc'
                subs = collect_dialogues_until_junction(cc)

                # Step B: build a ChoiceResult
                cr = ChoiceResult(
                    line=ln,
                    choice=choice_text,
                    condition=cond,
                    label=current_label,
                    # The test wants parent’s choice also in “previous_dialogues”
                    # so we keep both Dialogue and Choice from the path
                    previous_dialogues=[
                        x for x in path if isinstance(x, Dialogue) or isinstance(x, Choice)
                    ],
                    subsequent_dialogues=subs,
                )
                results.append(cr)

                # Step C: For nested blocks, we append the current choice to the path
                new_path = path[:] + [
                    Choice(line=ln, choice=choice_text, condition=cond, children=[])
                ]

                # Now walk deeper (unless next is a junction)
                for child in cc:
                    if not is_junction(child):
                        walk(child, new_path, current_label)

            # 7) Jump => skip or treat as a stop
            case Jump():
                pass

            # fallback
            case _:
                raise ValueError(f"Unknown node type: {node}")

    # Kick off with an empty path
    walk(script, [], None)
    return results


def collect_dialogues_until_junction(children: list) -> list[Dialogue]:
    """
    Gathers Dialogue objects from these children until hitting a branching node.
    The test doesn't want other node types in 'subsequent_dialogues'—only Dialogue.
    """
    found = []
    for child in children:
        if is_junction(child):
            break
        match child:
            case Dialogue():
                found.append(child)
            # If there's a label or block, you can recurse if you want
            # but the test presumably only wants direct lines.
            case _:
                pass
    return found


def extract_choices_from_script(path: Path):
    script = parse_script(path)
    choices = extract_choices(script)
    rich.print(choices)
    return choices


if __name__ == "__main__":
    typer.run(extract_choices_from_script)
