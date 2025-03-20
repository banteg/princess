import re


def clean_choice_for_voice(choice):
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

    rewrites = {
        "N-no. I w-won't t-tell you.": "No, I won't tell you.",
    }

    return rewrites.get(choice, choice) if choice else None
