from pathlib import Path

from princess.choices import ChoiceResult, extract_choices, get_voice_output_path
from princess.parser import Choice, Dialogue, parse_script
from princess.text import clean_choice_for_voice

DIALOGUE = [
    Dialogue(line=3, character="n", dialogue="narrator_line_1", voice="narrator_audio_1"),
    Dialogue(line=5, character="n", dialogue="narrator_line_2", voice="narrator_audio_2"),
    Dialogue(line=11, character="n", dialogue="narrator_line_3", voice="narrator_audio_3"),
    Dialogue(line=15, character="n", dialogue="narrator_line_4", voice="narrator_audio_4"),
    Dialogue(line=19, character="n", dialogue="narrator_line_5", voice="narrator_audio_5"),
    Dialogue(line=22, character="n", dialogue="narrator_line_6", voice="narrator_audio_6"),
]
CHOSEN = [
    Choice(line=12, choice="• choice_3", condition="condition_3 == False", children=[]),
]


def create_choice_result(line, label, choice, condition, previous, subsequent, path):
    cleaned = clean_choice_for_voice(choice)
    output_path = get_voice_output_path(choice)
    return ChoiceResult(
        line=line,
        label=label,
        choice=choice,
        condition=condition,
        previous_dialogues=previous,
        subsequent_dialogues=subsequent,
        path=path,
        clean=cleaned,
        output=output_path,
    )


CHOICES = [
    create_choice_result(
        line=8,
        label="main_dialogue",
        choice="• choice_1",
        condition="condition_1 == False",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[],
        path="tests/data/micro_script.rpy",
    ),
    create_choice_result(
        line=9,
        label="main_dialogue",
        choice="• choice_2",
        condition="condition_2 == False",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[DIALOGUE[2]],
        path="tests/data/micro_script.rpy",
    ),
    create_choice_result(
        line=12,
        label="main_dialogue",
        choice="• choice_3",
        condition="condition_3 == False",
        previous=[DIALOGUE[0], DIALOGUE[1]],
        subsequent=[DIALOGUE[3]],
        path="tests/data/micro_script.rpy",
    ),
    create_choice_result(
        line=17,
        label="nested_sequence",
        choice="• nested_choice_1",
        condition="can_proceed",
        previous=[DIALOGUE[0], DIALOGUE[1], CHOSEN[0], DIALOGUE[3]],
        subsequent=[DIALOGUE[4]],
        path="tests/data/micro_script.rpy",
    ),
    create_choice_result(
        line=20,
        label="nested_sequence",
        choice="• nested_choice_2",
        condition=None,
        previous=[DIALOGUE[0], DIALOGUE[1], CHOSEN[0], DIALOGUE[3]],
        subsequent=[DIALOGUE[5]],
        path="tests/data/micro_script.rpy",
    ),
    create_choice_result(
        line=23,
        label="nested_sequence",
        choice="• nested_choice_3",
        condition=None,
        previous=[DIALOGUE[0], DIALOGUE[1], CHOSEN[0], DIALOGUE[3]],
        subsequent=[],
        path="tests/data/micro_script.rpy",
    ),
]


def test_parse_full_match():
    script_path = Path("tests/data/micro_script.rpy")
    ast_tree = parse_script(script_path)
    parsed = extract_choices(ast_tree, script_path)

    # Check that each parsed result matches the expected format/structure
    for i, result in enumerate(parsed):
        expected = CHOICES[i]
        assert expected == result
