import re

import rich

from princess.characters import extract_characters
from princess.models import Dialogue, Choice, ChoiceResult

rewrites = {
    "N-no. I w-won't t-tell you.": "No, I won't tell you.",
}
replacements = {
    "'Mr. Anatomy'": "Mr. Anatomy",
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
    unwanted_re = re.compile(r"Ugh!|\(|\)")
    special_re = re.compile(
        r"^(Say|Join|Follow|Play|Return|Make|Continue|Ignore|Embrace|Investigate|Go|Do|Drop|Tighten|Kneel|Force|Try)\s"
    )

    choice = bullet_re.sub("", choice)
    choice = formatting_re.sub("", choice)
    choice = prefixes_re.sub("", choice)
    choice = actions_re.sub("", choice)
    choice = unwanted_re.sub("", choice)

    for old, new in replacements.items():
        choice = choice.replace(old, new)

    # quoted text is 100% spoken dialogue
    if quoted_text := quoted_text_re.findall(choice):
        return " ".join(quoted_text)

    # non-verbal lines
    if special_re.search(choice):
        return None

    return rewrites.get(choice, choice) if choice else None


def print_dialogue(item: Dialogue | Choice, offset: int | None = None):
    characters = extract_characters()
    offset_text = f"[blue]{offset:+>2}[/] " if offset is not None else ""

    match item:
        case Dialogue(character=character, dialogue=dialogue):
            rich.print(
                f"{offset_text}[yellow]{characters[character]}[/]: [dim]{strip_formatting(dialogue)}"
            )
        case Choice(choice=choice):
            rich.print(f"{offset_text}[red]Choice:[/] {strip_formatting(choice)}")


def print_dialogues(items: list[Dialogue | Choice]):
    for item in items:
        print_dialogue(item)


def print_choice_context(choice: ChoiceResult):
    # Print dialogues before the choice with negative numbers
    for i, dialogue in enumerate(choice.previous_dialogues[-3:]):
        # Calculate relative position (-3, -2, or -1)
        offset = i - len(choice.previous_dialogues[-3:])
        print_dialogue(dialogue, offset)

    # Print the main choice at position 0
    rich.print(f"[blue] 0[/] [bold magenta]Voiced: [bold blue]{choice.clean}")
    rich.print(f"[blue] 0[/] [bold magenta]Choice:[/] [dim]{strip_formatting(choice.choice)}")

    # Print dialogues after the choice with positive numbers
    for i, dialogue in enumerate(choice.subsequent_dialogues[:3], 1):
        print_dialogue(dialogue, i)
