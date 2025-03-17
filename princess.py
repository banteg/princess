import marimo

__generated_with = "0.11.20"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        # Slay the Princess

        some tools that simplify hacking on the game written by [banteg](https://x.com/bantg)

        - [x] walk script files
        - [x] extract character ids
        - [x] extract voice lines
        - [x] extract menu choices
        - [x] find labels and jumps
        - [ ] extract dialogue context for choices
        - [ ] explore voice lines
        """
    )
    return


@app.cell
def _(Path, os):
    GAME_PATH = Path(os.environ["GAME_PATH"])
    return (GAME_PATH,)


@app.cell
def _(GAME_PATH, Path, re):
    def walk_script_files():
        """
        Iterate over all script files
        """
        for path in GAME_PATH.rglob("*.rpy"):
            yield path


    def extract_characters():
        """
        Extract all character identifiers
        """
        CHARACTER_RE = re.compile(r"^define (.*?) = Character\(")
        for path in walk_script_files():
            for line in Path(path).read_text().splitlines():
                if match := CHARACTER_RE.search(line.lstrip()):
                    yield match.group(1)
    return extract_characters, walk_script_files


@app.cell
def _(extract_characters):
    characters = list(extract_characters())
    "|".join(characters)
    return (characters,)


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Voice lines

        These are spoken lines in the game.
        """
    )
    return


@app.cell
def _(GAME_PATH, Path, extract_characters, pl, re, walk_script_files):
    def extract_voice_lines(path=None):
        """
        Extract all spoken lines with their corresponding voice file, character, and line.
        """
        paths = [Path(path)] if path is not None else walk_script_files()
        characters = extract_characters()
        voice_regex = re.compile(
            r'^(?P<indent>\s*)voice\s+"(?P<voice>[^"]+)"', re.MULTILINE
        )
        character_regex = re.compile(
            r"^(?P<indent>\s*)(?P<character>"
            + "|".join(characters)
            + r')\s"(?P<dialogue>[^"]+)(?P<closed>"?)',
            re.MULTILINE,
        )
        label_re = re.compile(r"^\s*label ([a-z]\w+):$")
        for path in paths:
            current_label = None
            current_indent = None
            continue_dialogue = None
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if label_match := label_re.search(line):
                    current_label = label_match.group(1)
                if voice_match := voice_regex.search(line):
                    current_indent = voice_match.group("indent")
                    path_clean = str(path.relative_to(GAME_PATH))
                    current = {
                        "key": f"{path_clean}:{i:05d}",
                        "path": path_clean,
                        "lineno": i,
                        "label": current_label,
                        "voice": voice_match.group("voice"),
                    }
                    continue_dialogue = False
                elif char_match := character_regex.search(line):
                    if char_match.group("indent") != current_indent:
                        continue
                    current.update(
                        {
                            "character": char_match.group("character"),
                            "dialogue": char_match.group("dialogue"),
                        }
                    )
                    continue_dialogue = char_match.group("closed") != '"'
                    if not continue_dialogue:
                        yield current
                elif continue_dialogue:
                    match = re.search(r'\s*([^"]+)"', line)
                    print("extending line")
                    print(line)
                    current["dialogue"] += f" {match.group(1)}"
                    continue_dialogue = False
                    yield current


    voice_lines = pl.DataFrame(extract_voice_lines())
    voice_lines
    return extract_voice_lines, voice_lines


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Menu choices

        These are what the hero can say, think, or do.
        """
    )
    return


@app.cell
def _(GAME_PATH, Path, pl, re, walk_script_files):
    def extract_choices(path=None):
        paths = [Path(path)] if path is not None else walk_script_files()
        menu_re = re.compile(r"(?P<indent>^\s+)menu:")
        option_re = re.compile(r'(?P<indent>^\s+)"(?P<option>[^"]+)"')
        label_re = re.compile(r"^\s*label ([a-z]\w+):$")
        for path in paths:
            indent = None
            menu_index = 0
            current_label = None
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if label_match := label_re.search(line):
                    current_label = label_match.group(1)
                if menu := menu_re.search(line):
                    indent = len(menu.group("indent"))
                    menu_index += 1
                if option := option_re.search(line):
                    if indent is None or len(option.group("indent")) != indent + 4:
                        continue
                    path_clean = str(path.relative_to(GAME_PATH))
                    yield {
                        "key": f"{path_clean}:{i:05d}",
                        "path": path_clean,
                        "lineno": i,
                        "label": current_label,
                        "menu": menu_index,
                        "option": option.group("option"),
                    }


    menu_choices = pl.DataFrame(extract_choices())
    menu_choices
    return extract_choices, menu_choices


@app.cell
def _(GAME_PATH, extract_characters, pl, re, walk_script_files):
    def extract_dialogue_and_choices():
        characters = extract_characters()

        # Compile regex patterns
        voice_regex = re.compile(
            r'^(?P<indent>\s*)voice\s+"(?P<voice>[^"]+)"', re.MULTILINE
        )
        character_regex = re.compile(
            r"^(?P<indent>\s*)(?P<character>"
            + "|".join(characters)
            + r')\s"(?P<dialogue>[^"]+)(?P<closed>"?)',
            re.MULTILINE,
        )
        label_re = re.compile(r"^\s*label ([a-z]\w+):$")
        menu_re = re.compile(r"(?P<indent>^\s+)menu:")
        option_re = re.compile(r'(?P<indent>^\s+)"(?P<option>[^"]+)"')

        for path in walk_script_files():
            path_clean = str(path.relative_to(GAME_PATH))
            current_label = None
            current_indent = None
            continue_dialogue = None
            current = None

            menu_indent = None
            menu_index = 0

            for i, line in enumerate(path.read_text().splitlines(), 1):
                # Check for label definitions
                if label_match := label_re.search(line):
                    current_label = label_match.group(1)

                # Check for voice lines
                if voice_match := voice_regex.search(line):
                    current_indent = voice_match.group("indent")
                    current = {
                        "key": f"{path_clean}:{i:05d}",
                        "path": path_clean,
                        "lineno": i,
                        "label": current_label,
                        "voice": voice_match.group("voice"),
                        "type": "voice_line",
                    }
                    continue_dialogue = False
                elif char_match := character_regex.search(line):
                    if char_match.group("indent") != current_indent:
                        continue
                    current.update(
                        {
                            "character": char_match.group("character"),
                            "dialogue": char_match.group("dialogue"),
                        }
                    )
                    continue_dialogue = char_match.group("closed") != '"'
                    if not continue_dialogue:
                        yield current
                elif continue_dialogue:
                    match = re.search(r'\s*([^"]+)"', line)
                    if match:
                        print("extending line")
                        print(line)
                        current["dialogue"] += f" {match.group(1)}"
                        continue_dialogue = False
                        yield current

                # Check for menu choices
                if menu_match := menu_re.search(line):
                    menu_indent = len(menu_match.group("indent"))
                    menu_index += 1
                if option_match := option_re.search(line):
                    if (
                        menu_indent is None
                        or len(option_match.group("indent")) != menu_indent + 4
                    ):
                        continue
                    yield {
                        "key": f"{path_clean}:{i:05d}",
                        "path": path_clean,
                        "lineno": i,
                        "label": current_label,
                        "menu": menu_index,
                        "option": option_match.group("option"),
                        "type": "menu_choice",
                    }


    lines_and_choices = pl.DataFrame(extract_dialogue_and_choices())
    lines_and_choices
    return extract_dialogue_and_choices, lines_and_choices


@app.cell
def _(lines_and_choices, pl, re):
    import random

    choices_todo = (
        lines_and_choices.filter(
            (
                pl.col("type") == "menu_choice"
                # & (
                #     pl.col("path")
                #     == "scripts/paths/stranger/stranger_1/stranger_1_cabin.rpy"
                # )
            )
        )
        .unique("option")
        .sort("key")["option"]
        .to_list()
    )
    # Path('output/choices_sample.txt').write_text('\n'.join(choices_todo))


    def clean_choice_for_tts(choice):
        bullet_re = re.compile(r"•\s+")
        formatting_re = re.compile(r"\{[^\}]+\}")
        prefixes_re = re.compile(r"\([^\)]+\)\s+")
        actions_re = re.compile(r"\[\[[^]]+\]")
        quoted_text_re = re.compile(r"''(.+?)''")
        special_re = re.compile(
            r"^(Say|Join|Follow|Return|Make|Continue|Ignore|Investigate|Go|Do|Drop|Tighten|Kneel|Force)\s"
        )
        choice = bullet_re.sub("", choice)
        choice = formatting_re.sub("", choice)
        choice = prefixes_re.sub("", choice)
        choice = actions_re.sub("", choice)

        # quoted text is 100% spoken dialogue
        if quoted_text := quoted_text_re.findall(choice):
            return "\n".join(quoted_text)

        # non-verbal lines
        if special_re.search(choice):
            return None

        rewrites = {
            "N-no. I w-won't t-tell you.": "No, I won't tell you.",
        }

        return rewrites.get(choice, choice) if choice else None


    cleaned_tts = [{"choice": c, "clean": clean_choice_for_tts(c)} for c in choices_todo]
    pl.DataFrame(cleaned_tts).write_csv("output/hero_lines.csv")
    return choices_todo, clean_choice_for_tts, cleaned_tts, random


@app.cell
def _(mo):
    mo.md(
        r"""
        # Context for hero's lines

        merge dialogue and option to create context for audio generation

        13187 lines
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Labels and jumps

        These are all the paths a hero can take.
        """
    )
    return


@app.cell
def _(GAME_PATH, pl, re, walk_script_files):
    def find_labels_and_jumps():
        # first collect all labels metadata
        label_re = re.compile(r"^\s*label ([a-z]\w+):$")
        jump_re = re.compile(r"^\s*jump (\w+)$")
        labels = {}
        for path in walk_script_files():
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if label := label_re.search(line):
                    labels[label.group(1)] = {
                        "path": str(path.relative_to(GAME_PATH)),
                        "lineno": i,
                    }
        # now find all jumps and attribute their dest correctly
        jumps = {}
        for path in walk_script_files():
            current_label = None
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if match_label := label_re.search(line):
                    current_label = match_label.group(1)
                if jump := jump_re.search(line):
                    label = labels[jump.group(1)]
                    yield {
                        "src_line": f"{path.relative_to(GAME_PATH)}:{i}",
                        "dst_line": f"{label['path']}:{label['lineno']}",
                        "src_label": current_label,
                        "dst_label": jump.group(1),
                    }


    labels_jumps = pl.DataFrame(find_labels_and_jumps())
    labels_jumps
    return find_labels_and_jumps, labels_jumps


@app.cell
def _(defaultdict, labels_jumps, nx):
    def jumps_to_graph(jumps):
        g = nx.DiGraph()
        seen = defaultdict(int)
        for row in jumps:
            seen[row["src_label"]] += 1
            g.add_edge(
                row["src_label"],
                row["dst_label"],
                # src_label=row["src_label"],
                # dst_label=row["dst_label"],
            )

        print(len(seen), seen)
        return g


    jumps = labels_jumps.to_dicts()
    nx.write_graphml(jumps_to_graph(jumps), "output/jumps.graphml")
    return jumps, jumps_to_graph


@app.cell
def _():
    from pathlib import Path
    import networkx as nx
    from collections import defaultdict
    import marimo as mo
    import polars as pl
    import re
    import os
    import json
    return Path, defaultdict, json, mo, nx, os, pl, re


@app.cell
def _(mo):
    mo.md(
        r"""
        ---
        # old code below
        """
    )
    return


@app.cell
def _(re):
    def clean_text_for_voice(text):
        for stop in ["• ", "Say nothing."]:
            text = text.replace(stop, "")
        for stress in ["{b}"]:
            text = text.replace(stress, ", ")
        for markup in [r"\(.+?\)", r"\[.+?\]", r"\{.+?\}"]:
            text = re.sub(markup, "", text)
        text = re.sub(r'"(.+?)"', r"\1", text)  # remove quotes
        text = text.replace("''", '"')
        return text.strip()
    return (clean_text_for_voice,)


if __name__ == "__main__":
    app.run()
