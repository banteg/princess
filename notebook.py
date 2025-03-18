import marimo

__generated_with = "0.11.20"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        # Slay the Princess

        tools that simplify hacking on the game written by [banteg](https://x.com/bantg)

        - [x] walk script files
        - [x] extract character ids
        - [x] extract voice lines
        - [x] extract menu choices
        - [x] find labels and jumps
        - [ ] extract dialogue context for choices
        - [ ] explore voice lines
        
        *Note: Core functions have been moved to the `princess` package*
        """
    )
    return


@app.cell
def _(Path, os):
    GAME_PATH = Path(os.environ["GAME_PATH"])
    return (GAME_PATH,)


@app.cell
def _():
    from princess.utils import (
        walk_script_files,
        extract_characters,
        extract_voice_lines,
        extract_choices,
        extract_dialogue_and_choices,
        find_labels_and_jumps,
        jumps_to_graph,
        clean_choice_for_tts,
        clean_text_for_voice,
    )

    return (
        walk_script_files,
        extract_characters,
        extract_voice_lines,
        extract_choices,
        extract_dialogue_and_choices,
        find_labels_and_jumps,
        jumps_to_graph,
        clean_choice_for_tts,
        clean_text_for_voice,
    )


@app.cell
def _():
    from princess.utils import extract_characters

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
def _():
    from princess.utils import extract_voice_lines
    import polars as pl

    voice_lines = pl.DataFrame(extract_voice_lines())
    voice_lines
    return voice_lines


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
def _():
    from princess.utils import extract_choices
    import polars as pl

    menu_choices = pl.DataFrame(extract_choices())
    menu_choices
    return menu_choices


@app.cell
def _():
    from princess.utils import extract_dialogue_and_choices
    import polars as pl

    lines_and_choices = pl.DataFrame(extract_dialogue_and_choices())
    lines_and_choices
    return lines_and_choices


@app.cell
def _():
    from princess.utils import clean_choice_for_tts
    import polars as pl
    import random
    from pathlib import Path

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

    cleaned_tts = [{"choice": c, "clean": clean_choice_for_tts(c)} for c in choices_todo]
    Path("output").mkdir(exist_ok=True)
    pl.DataFrame(cleaned_tts).write_parquet("output/hero_lines.parquet")
    return choices_todo, cleaned_tts, random


@app.cell
def _(characters):
    " ".join(characters)
    return


@app.cell
def _(characters):
    print("|".join(characters))
    return


app._unparsable_cell(
    r"""
    def extract_choices_with_context(path):
        label_re = re.compile(r\"^\s*label\s+(\w+):\")
        character_re = re.compile(r\"^\s*(\" + \"|\".join(characters) + r\")\s+\\"(.+)\\"\")
        menu_re = re.compile(r\"^\s*menu:\")
        choice_re = re.compile(r'^\s+\\"(.+?)\\"')
        voice_re = re.compile(r'^\s*voice\s+\"([^\"]+)\"')

        current_label = None

        for line in Path(path).read_text().splitlines():
            if label_match := label_re.search(line):
                current_label = label_match.group(1)
                 print(f'new label: {current_label}')


    extract_choices_with_context('script.rpy')
    """,
    name="_",
)


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
def _():
    from princess.utils import find_labels_and_jumps
    import polars as pl

    labels_jumps = pl.DataFrame(find_labels_and_jumps())
    labels_jumps
    return labels_jumps


@app.cell
def _():
    from princess.utils import jumps_to_graph
    import networkx as nx
    from pathlib import Path

    jumps = labels_jumps.to_dicts()
    graph = jumps_to_graph(jumps)
    Path("output").mkdir(exist_ok=True)
    nx.write_graphml(graph, "output/jumps.graphml")
    return jumps, graph


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
    from parsimonious.grammar import Grammar
    from parsimonious.nodes import NodeVisitor
    import pprint

    return (
        Grammar,
        NodeVisitor,
        Path,
        defaultdict,
        json,
        mo,
        nx,
        os,
        pl,
        pprint,
        re,
    )


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
