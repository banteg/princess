from pathlib import Path
from princess.parser import Choice, Dialogue, grammar, ChoicesTransformer, clean_script

SCRIPT = clean_script("tests/data/micro_script.rpy")

DIALOGUE = [
    Dialogue(line=3, character="n", text="narrator_line_1", voice="narrator_audio_1"),
    Dialogue(line=5, character="n", text="narrator_line_2", voice="narrator_audio_2"),
    Dialogue(line=11, character="n", text="narrator_line_3", voice="narrator_audio_3"),
    Dialogue(line=15, character="n", text="narrator_line_4", voice="narrator_audio_4"),
    Dialogue(line=19, character="n", text="narrator_line_5", voice="narrator_audio_5"),
    Dialogue(line=22, character="n", text="narrator_line_6", voice="narrator_audio_6"),
]

CHOICES = choices = [
    Choice(
        line=8,
        label="main_dialogue",
        choice="• choice_1",
        condition="condition_1 == False",
        prev_dialogue=[DIALOGUE[0], DIALOGUE[1]],
        next_dialogue=[],
    ),
    Choice(
        line=9,
        label="main_dialogue",
        choice="• choice_2",
        condition="condition_2 == False",
        prev_dialogue=[DIALOGUE[0], DIALOGUE[1]],
        next_dialogue=[DIALOGUE[2]],
    ),
    Choice(
        line=12,
        label="main_dialogue",
        choice="• choice_3",
        condition="condition_3 == False",
        prev_dialogue=[DIALOGUE[0], DIALOGUE[1]],
        next_dialogue=[DIALOGUE[3]],
    ),
    Choice(
        line=17,
        label="nested_sequence",
        choice="• nested_choice_1",
        condition="can_proceed",
        prev_dialogue=[DIALOGUE[3]],
        next_dialogue=[DIALOGUE[4]],
    ),
    Choice(
        line=24,
        label="nested_sequence",
        choice="• nested_choice_2",
        condition=None,
        prev_dialogue=[DIALOGUE[3]],
        next_dialogue=[DIALOGUE[5]],
    ),
    Choice(
        line=28,
        label="nested_sequence",
        choice="• nested_choice_3",
        condition=None,
        prev_dialogue=[DIALOGUE[3]],
        next_dialogue=[],
    ),
]


def test_script_clean():
    assert Path("tests/data/micro_script.rpy").read_text().strip() == SCRIPT


def test_parse_script():
    result = grammar.parse(SCRIPT)
    transformed = ChoicesTransformer().transform(result)
    assert transformed == CHOICES
