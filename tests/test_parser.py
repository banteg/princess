from princess.parser import Choice, Dialogue, grammar, ChoicesTransformer

SCRIPT = """label start:
    voice "audio/voices/ch1/woods/narrator/script_n_1.flac"
    n "You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n"
    voice "audio/voices/ch1/woods/narrator/script_n_2.flac"
    n "You're here to slay her. If you don't, it will be the end of the world.\n"
    label forest_dialogue:
        menu:
            "{i}• (Explore) The end of the world? What are you talking about?{/i}" if forest_1_questioning_start == False:
                voice "audio/voices/ch1/woods/narrator/script_n_3.flac"
                n "I'm talking about the end of everything as we know it. No more birds, no more trees, and, perhaps most problematically of all, no more people. You have to put an end to her.\n"
            "{i}• (Explore) Have you considered that maybe the only reason she's going to end the world is {b}because{/b} she's locked up?{/i}" if forest_1_casuality_explore == False:
                voice "audio/voices/ch1/woods/narrator/script_n_8.flac"
                n "While I appreciate the mental exercise, we are running up against a bit of a ticking clock.\n"
                voice "audio/voices/ch1/woods/narrator/script_n_9.flac"
                n "Nevertheless, let me assure you: the Princess is locked up because she's dangerous, she is not dangerous because she's locked up.\n"
            "{i}• [[Turn around and leave.]{/i}" if stranger_encountered == False:
                label turn_and_leave_join:
                    voice "audio/voices/ch1/woods/narrator/script_n_28.flac"
                    n "Seriously? You're just going to turn around and leave? Do you even know where you're going?\n"
                    menu:
                        "{i}• Okay, fine. You're persistent. I'll go to the cabin and I'll slay the Princess. Ugh!{/i}" if ch1_can_cabin:
                            voice "audio/voices/ch1/woods/narrator/script_n_29.flac"
                            n "{i}Thank you{/i}! The whole world owes you a debt of gratitude. Really.\n"
                                    voice "audio/voices/ch1/voices/ch1_stubborn_1.flac"
                                    stubborn "Oh, about {i}time{/i}. I can't believe you were about to run away.\n"
                        "{i}• Okay, fine. I'll go to the cabin and I'll talk to the Princess. Maybe I'll slay her. Maybe I won't. I guess we'll see.{/i}" if ch1_can_cabin:
                            voice "audio/voices/ch1/woods/narrator/script_n_30.flac"
                            n "I guess we will.\n"
                                    voice "audio/voices/ch1/voices/ch1_stubborn_1.flac"
                                    stubborn "Oh, about {i}time{/i}. I can't believe you were about to run away.\n"
                        "{i}• (Lie) Yes, I definitely know where I'm going.{/i}":
                            voice "audio/voices/ch1/woods/narrator/script_n_31.flac"
                            n "Somehow I doubt that, but fine.\n"
                            voice "audio/voices/ch1/woods/narrator/script_n_32.flac"
                            n "I suppose you just quietly continue down the path away from the cabin.\n"
                        "{i}• Nope!{/i}":
                        "{i}• The only thing that matters is where I'm not going. (The cabin. I am not going to the cabin.){/i}":
"""

CHOICES = [
    Choice(
        line=8,
        label=None,
        choice="{i}• (Explore) The end of the world? What are you talking about?{/i}",
        condition="forest_1_questioning_start == False",
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=10,
                character="n",
                text="I'm talking about the end of everything as we know it. No more birds, no more trees, and, perhaps most problematically of all, no more people. You have to put an end to her.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_3.flac",
            )
        ],
    ),
    Choice(
        line=11,
        label=None,
        choice="{i}• (Explore) Have you considered that maybe the only reason she's going to end the world is {b}because{/b} she's locked up?{/i}",
        condition="forest_1_casuality_explore == False",
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=13,
                character="n",
                text="While I appreciate the mental exercise, we are running up against a bit of a ticking clock.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_8.flac",
            ),
            Dialogue(
                line=15,
                character="n",
                text="Nevertheless, let me assure you: the Princess is locked up because she's dangerous, she is not dangerous because she's locked up.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_9.flac",
            ),
        ],
    ),
    Choice(
        line=16,
        label="turn_and_leave_join",
        choice="{i}• [[Turn around and leave.]{/i}",
        condition="stranger_encountered == False",
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            )
        ],
    ),
    Choice(
        line=21,
        label=None,
        choice="{i}• Okay, fine. You're persistent. I'll go to the cabin and I'll slay the Princess. Ugh!{/i}",
        condition="ch1_can_cabin",
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=23,
                character="n",
                text="{i}Thank you{/i}! The whole world owes you a debt of gratitude. Really.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_29.flac",
            ),
            Dialogue(
                line=25,
                character="stubborn",
                text="Oh, about {i}time{/i}. I can't believe you were about to run away.\n",
                voice="audio/voices/ch1/voices/ch1_stubborn_1.flac",
            ),
        ],
    ),
    Choice(
        line=26,
        label=None,
        choice="{i}• Okay, fine. I'll go to the cabin and I'll talk to the Princess. Maybe I'll slay her. Maybe I won't. I guess we'll see.{/i}",
        condition="ch1_can_cabin",
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=28,
                character="n",
                text="I guess we will.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_30.flac",
            ),
            Dialogue(
                line=30,
                character="stubborn",
                text="Oh, about {i}time{/i}. I can't believe you were about to run away.\n",
                voice="audio/voices/ch1/voices/ch1_stubborn_1.flac",
            ),
        ],
    ),
    Choice(
        line=31,
        label=None,
        choice="{i}• (Lie) Yes, I definitely know where I'm going.{/i}",
        condition=None,
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            ),
        ],
        next_dialogue=[
            Dialogue(
                line=31,
                character="n",
                text="Somehow I doubt that, but fine.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_31.flac",
            ),
            Dialogue(
                line=32,
                character="n",
                text="I suppose you just quietly continue down the path away from the cabin.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_32.flac",
            ),
        ],
    ),
    Choice(
        line=36,
        label=None,
        choice="{i}• Nope!{/i}",
        condition=None,
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            ),
        ],
        next_dialogue=[],
    ),
    Choice(
        line=37,
        label=None,
        choice="{i}• The only thing that matters is where I'm not going. (The cabin. I am not going to the cabin.){/i}",
        condition=None,
        prev_dialogue=[
            Dialogue(
                line=3,
                character="n",
                text="You're on a path in the woods. And at the end of that path is a cabin. And in the basement of that cabin is a princess.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_1.flac",
            ),
            Dialogue(
                line=5,
                character="n",
                text="You're here to slay her. If you don't, it will be the end of the world.\n",
                voice="audio/voices/ch1/woods/narrator/script_n_2.flac",
            ),
            Dialogue(
                line=19,
                character="n",
                text="Seriously? You're just going to turn around and leave? Do you even know where you're going?\n",
                voice="audio/voices/ch1/woods/narrator/script_n_28.flac",
            ),
        ],
        next_dialogue=[],
    ),
]


def test_parse_script():
    result = grammar.parse(SCRIPT)
    transformed = ChoicesTransformer().transform(result)
    assert transformed == CHOICES
