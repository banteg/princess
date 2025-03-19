from princess.parser import Choice, Dialogue, grammar, ChoicesTransformer

SCRIPT = """\
label start:
    voice "narrator_audio_1"
    n "narrator_line_1"
    voice "narrator_audio_2"
    n "narrator_line_2"
    label main_dialogue:
        menu:
            "choice_1" if condition_1 == False:
            "choice_2" if condition_2 == False:
                voice "response_audio_1"
                n "narrator_line_3"
            "choice_3" if condition_3 == False:
                label nested_sequence:
                    voice "response_audio_2"
                    n "narrator_line_4"
                    menu:
                        "nested_choice_1" if can_proceed:
                            voice "nested_audio_1"
                            n "narrator_line_5"
                        "nested_choice_2":
                            voice "nested_audio_2"
                            n "narrator_line_6"
                        "nested_choice_3":
"""

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


def test_parse_script():
    result = grammar.parse(SCRIPT)
    transformed = ChoicesTransformer().transform(result)
    assert transformed == CHOICES
