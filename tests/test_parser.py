from pathlib import Path
from princess.parser import Choice, Dialogue, grammar, ChoicesTransformer, clean_script

SCRIPT = clean_script("tests/data/micro_script.rpy")

CHOICES = choices = [
    Choice(
        line=7,
        label="main_dialogue",
        choice="choice_1",
        condition="condition_1 == False",
        prev_dialogue=[
            Dialogue(line=2, character="n", text="narrator_line_1", voice="narrator_audio_1"),
            Dialogue(line=4, character="n", text="narrator_line_2", voice="narrator_audio_2"),
        ],
        next_dialogue=[],
    ),
    Choice(
        line=10,
        label="main_dialogue",
        choice="choice_2",
        condition="condition_2 == False",
        prev_dialogue=[
            Dialogue(line=2, character="n", text="narrator_line_1", voice="narrator_audio_1"),
            Dialogue(line=4, character="n", text="narrator_line_2", voice="narrator_audio_2"),
        ],
        next_dialogue=[
            Dialogue(line=11, character="n", text="narrator_line_3", voice="response_audio_1")
        ],
    ),
    Choice(
        line=14,
        label="main_dialogue",
        choice="choice_3",
        condition="condition_3 == False",
        prev_dialogue=[
            Dialogue(line=2, character="n", text="narrator_line_1", voice="narrator_audio_1"),
            Dialogue(line=4, character="n", text="narrator_line_2", voice="narrator_audio_2"),
        ],
        next_dialogue=[
            Dialogue(line=16, character="n", text="narrator_line_4", voice="response_audio_2")
        ],
    ),
    Choice(
        line=20,
        label="nested_sequence",
        choice="nested_choice_1",
        condition="can_proceed",
        prev_dialogue=[
            Dialogue(line=16, character="n", text="narrator_line_4", voice="response_audio_2")
        ],
        next_dialogue=[
            Dialogue(line=21, character="n", text="narrator_line_5", voice="nested_audio_1")
        ],
    ),
    Choice(
        line=24,
        label="nested_sequence",
        choice="nested_choice_2",
        condition=None,
        prev_dialogue=[
            Dialogue(line=16, character="n", text="narrator_line_4", voice="response_audio_2")
        ],
        next_dialogue=[
            Dialogue(line=25, character="n", text="narrator_line_6", voice="nested_audio_2")
        ],
    ),
    Choice(
        line=28,
        label="nested_sequence",
        choice="nested_choice_3",
        condition=None,
        prev_dialogue=[
            Dialogue(line=16, character="n", text="narrator_line_4", voice="response_audio_2")
        ],
        next_dialogue=[],
    ),
]


def test_script_clean():
    assert Path("tests/data/micro_script.rpy").read_text().strip() == SCRIPT


def test_parse_script():
    result = grammar.parse(SCRIPT)
    transformed = ChoicesTransformer().transform(result)
    assert transformed == CHOICES
