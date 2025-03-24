import re

import rich

from princess.characters import extract_characters
from princess.choices import ChoiceResult
from princess.parser import Choice, Dialogue

rewrites = {
    "N-no. I w-won't t-tell you.": "No, I won't tell you.",
}


def strip_formatting(text: str):
    text = re.sub(r"\{[^}]+\}", "", text)
    text = text.replace("''", '"')
    text = text.replace("\\n", "")
    return text


def clean_choice_for_voice(choice: str) -> str | None:
    """
    Clean menu choice text for text-to-speech processing.

    Args:
        choice: The raw choice text

    Returns:
        Cleaned text suitable for TTS, or None if not applicable
    """
    bullet_re = re.compile(r"•\s+")
    formatting_re = re.compile(r"\{[^\}]+\}")
    prefixes_re = re.compile(r"\([^\)]+\)\s+")
    actions_re = re.compile(r"\[\[[^]]+\]")
    quoted_text_re = re.compile(r"''(.+?)''")
    special_re = re.compile(
        r"^(Say|Join|Follow|Play|Return|Make|Continue|Ignore|Embrace|Investigate|Go|Do|Drop|Tighten|Kneel|Force|Try)\s"
    )

    choice = bullet_re.sub("", choice)
    choice = formatting_re.sub("", choice)
    choice = prefixes_re.sub("", choice)
    choice = actions_re.sub("", choice)

    # quoted text is 100% spoken dialogue
    if quoted_text := quoted_text_re.findall(choice):
        return " ".join(quoted_text)

    # non-verbal lines
    if special_re.search(choice):
        return None

    return rewrites.get(choice, choice) if choice else None



def print_dialogues(items: list[Dialogue | Choice]):
    characters = extract_characters()
    for item in items:
        match item:
            case Dialogue(character=character, dialogue=dialogue):
                rich.print(f"[yellow]{characters[character]}[/]: [dim]{strip_formatting(dialogue)}")
            case Choice(choice=choice):
                rich.print(f"[red]Choice:[/] [dim]{strip_formatting(choice)}")


def print_choice_context(choice: ChoiceResult):
    print_dialogues(choice.previous_dialogues[-3:])
    rich.print(f"[magenta]Choice:[/] {strip_formatting(choice.choice)}")
    rich.print(f"[magenta]Voiced: [bold blue]{choice.clean}")
    print_dialogues(choice.subsequent_dialogues[:3])
