label start:
    voice "narrator_audio_1"
    n "narrator_line_1"
    voice "narrator_audio_2"
    n "narrator_line_2"
    label main_dialogue:
        menu:
            "• choice_1" if condition_1 == False:
            "• choice_2" if condition_2 == False:
                voice "response_audio_1"
                n "narrator_line_3"
            "• choice_3" if condition_3 == False:
                label nested_sequence:
                    voice "response_audio_2"
                    n "narrator_line_4"
                    menu:
                        "• nested_choice_1" if can_proceed:
                            voice "nested_audio_1"
                            n "narrator_line_5"
                        "• nested_choice_2":
                            voice "nested_audio_2"
                            n "narrator_line_6"
                        "• nested_choice_3":
