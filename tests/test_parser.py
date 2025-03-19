from pathlib import Path

import pytest

from princess.parser import Choice, ChoicesTransformer, Dialogue, clean_script, grammar

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
        line=20,
        label="nested_sequence",
        choice="• nested_choice_2",
        condition=None,
        prev_dialogue=[DIALOGUE[3]],
        next_dialogue=[DIALOGUE[5]],
    ),
    Choice(
        line=23,
        label="nested_sequence",
        choice="• nested_choice_3",
        condition=None,
        prev_dialogue=[DIALOGUE[3]],
        next_dialogue=[],
    ),
]


def test_script_clean():
    assert Path("tests/data/micro_script.rpy").read_text().strip() == SCRIPT


def get_parsed():
    result = grammar.parse(SCRIPT)
    return ChoicesTransformer().transform(result)


def test_parse_num_choices():
    assert len(CHOICES) == len(get_parsed())


def test_parse_choice_lines():
    parsed = get_parsed()
    for choice, parsed_choice in zip(CHOICES, parsed):
        assert choice.line == parsed_choice.line


def test_parse_choice_labels():
    parsed = get_parsed()
    for choice, parsed_choice in zip(CHOICES, parsed):
        assert choice.label == parsed_choice.label


@pytest.mark.parametrize("index", range(len(CHOICES)))
def test_parse_full_match(index):
    parsed = get_parsed()
    assert CHOICES[index] == parsed[index]
