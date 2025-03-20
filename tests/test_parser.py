from pathlib import Path

from princess.parser import (
    ChoiceResult,
    Dialogue,
    RenpyTransformer,
    clean_script,
    extract_choices,
    grammar,
)

SCRIPT = clean_script("tests/data/micro_script.rpy")

DIALOGUE = [
    Dialogue(line=3, character="n", dialogue="narrator_line_1", voice="narrator_audio_1"),
    Dialogue(line=5, character="n", dialogue="narrator_line_2", voice="narrator_audio_2"),
    Dialogue(line=11, character="n", dialogue="narrator_line_3", voice="narrator_audio_3"),
    Dialogue(line=15, character="n", dialogue="narrator_line_4", voice="narrator_audio_4"),
    Dialogue(line=19, character="n", dialogue="narrator_line_5", voice="narrator_audio_5"),
    Dialogue(line=22, character="n", dialogue="narrator_line_6", voice="narrator_audio_6"),
]

CHOICES = [
    ChoiceResult(
        line=8,
        label="main_dialogue",
        choice="• choice_1",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[],
    ),
    ChoiceResult(
        line=9,
        label="main_dialogue",
        choice="• choice_2",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[DIALOGUE[2]],
    ),
    ChoiceResult(
        line=12,
        label="main_dialogue",
        choice="• choice_3",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[DIALOGUE[3]],
    ),
    ChoiceResult(
        line=17,
        label="nested_sequence",
        choice="• nested_choice_1",
        previous=[DIALOGUE[0], DIALOGUE[1], DIALOGUE[3]],
        subsequent=[DIALOGUE[4]],
    ),
    ChoiceResult(
        line=20,
        label="nested_sequence",
        choice="• nested_choice_2",
        previous=[DIALOGUE[0], DIALOGUE[1], DIALOGUE[3]],
        subsequent=[DIALOGUE[5]],
    ),
    ChoiceResult(
        line=23,
        label="nested_sequence",
        choice="• nested_choice_3",
        previous=[DIALOGUE[0], DIALOGUE[1], DIALOGUE[3]],
        subsequent=[],
    ),
]


def test_script_clean():
    assert Path("tests/data/micro_script.rpy").read_text().strip() == SCRIPT.strip()


def test_parse_full_match():
    raw_tree = grammar.parse(SCRIPT)
    ast_tree = RenpyTransformer().transform(raw_tree)
    parsed = extract_choices(ast_tree)
    assert CHOICES == parsed
