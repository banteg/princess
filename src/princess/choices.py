# Stage 3: Extract choices
# Here we extract choices and their surrounding dialogue by traversing the tree.
# The resulting list can be used for text-to-speech generation.
from dataclasses import dataclass

import typer

from princess.parser import Choice, Condition, Dialogue, Jump, Label, Menu, Script


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


def collect_dialogues_until_junction(children: list) -> list[Dialogue]:
    found = []
    for child in children:
        if is_junction(child):
            break
        match child:
            case Dialogue():
                found.append(child)
            case Label(label=lbl, children=subchildren):
                sub_found = collect_dialogues_until_junction(subchildren)
                found.extend(sub_found)
            case _:
                pass
    return found


def extract_choices(script: Script) -> list[ChoiceResult]:
    results: list[ChoiceResult] = []

    def walk(node, prev_dialogues: list[Dialogue], current_label: str | None):
        """
        Recursively traverse the script structure, collecting ChoiceResult.
        `prev_dialogues` accumulates Dialogue leading up to a branching point.
        `current_label` tracks the label name (if any).
        """
        match node:
            # Top-level script
            case Script(children=ch):
                for c in ch:
                    walk(c, prev_dialogues, current_label)

            # A label node
            case Label(label=lbl, children=ch):
                # update label context
                for child in ch:
                    walk(child, prev_dialogues[:], lbl)

            # A menu node => look for choice among children
            case Menu(children=ch):
                # Usually, a Menu has blocks or direct Choice objects in its children
                for child in ch:
                    walk(child, prev_dialogues, current_label)

            # A condition node
            case Condition(kind=k, condition=cond, children=ch):
                # If you consider condition a branching => maybe stop or skip
                # But typically you'd keep walking to find choices inside
                for child in ch:
                    walk(child, prev_dialogues, current_label)

            # A dialogue node => add it to prev_dialogues
            case Dialogue():
                prev_dialogues.append(node)

            case Choice(choice=choice_text, condition=cond, children=cc):
                # We found a choice => build a ChoiceResult
                # 1) subsequent dialogues from cc until a junction
                sub_dialogs = collect_dialogues_until_junction(cc)
                # 2) create a result
                cr = ChoiceResult(
                    line=node.line,
                    choice=choice_text,
                    condition=cond,
                    label=current_label,
                    previous_dialogues=prev_dialogues[:],
                    subsequent_dialogues=sub_dialogs,
                )
                results.append(cr)

                # If you want to keep traversing deeper for nested choices after we
                # gather subsequent, do so. Possibly we add sub_dialogs to prev?
                new_prev = prev_dialogues[:] + sub_dialogs
                for child in cc:
                    # skip if it's a junction, or continue if you want deeper menus
                    if not is_junction(child):
                        walk(child, new_prev, current_label)

            case Jump():
                pass

            # Fallback for unknown
            case _:
                raise ValueError(f"Unknown node: {node}")

    # Start
    walk(script, [], None)
    return results
