"""
Stage 3: Extract choices
We extract choices and their surrounding dialogue by traversing the Script tree.
The resulting list can be used for text-to-speech generation.
"""

from hashlib import sha256
from pathlib import Path

import rich
import typer
from rich.progress import track

from princess.game import get_game_path, walk_script_files
from princess.models import (
    Choice,
    ChoiceResult,
    ChoiceResultList,
    Condition,
    Dialogue,
    Jump,
    Label,
    Menu,
    Script,
)
from princess.parser import parse_script
from princess.text import clean_choice_for_voice

app = typer.Typer()


def get_voice_output_path(choice: str) -> Path:
    return Path("output/voice") / f"{sha256(choice.encode()).hexdigest()}.flac"


def extract_choices(script: Script, script_path: str | None = None) -> list[ChoiceResult]:
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
                    choice=choice_text,
                    condition=cond,
                    label=current_label,
                    previous_dialogues=path[:],
                    subsequent_dialogues=subs,
                    path=str(script_path),
                    line=ln,
                    clean=clean_choice_for_voice(choice_text),
                    output=get_voice_output_path(choice_text),
                )
                results.append(cr)

                # Step C: For nested blocks, we append the current choice to the path
                chosen = Choice(line=ln, choice=choice_text, condition=cond)
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


@app.command("choices")
def extract_choices_from_script(path: Path):
    script = parse_script(path)
    game_path = get_game_path()
    relative_path = path.relative_to(game_path) if path.is_relative_to(game_path) else path
    choices = extract_choices(script, script_path=relative_path)
    rich.print(choices)
    rich.print(f"Extracted {len(choices)} choices")
    Path("output/choices.json").write_text(
        ChoiceResultList(choices=choices).model_dump_json(indent=2)
    )
    return choices


@app.command("all-choices")
def extract_all_choices():
    extracted = ChoiceResultList(choices=[])
    game_scripts = list(walk_script_files())
    for path in track(game_scripts):
        script = parse_script(path)
        choices = extract_choices(script, script_path=path)
        rich.print(f"{path}: Extracted {len(choices)} choices")
        extracted.choices.extend(choices)

    rich.print(f"Extracted {len(extracted.choices)} choices from {len(game_scripts)} scripts")
    return extracted


if __name__ == "__main__":
    app()
