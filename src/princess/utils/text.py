"""Text processing utilities."""

import re


def clean_text_for_voice(text):
    """
    Clean text for voice processing by removing formatting and markup.
    
    Args:
        text: The text to clean
        
    Returns:
        Cleaned text suitable for voice processing
    """
    for stop in ["• ", "Say nothing."]:
        text = text.replace(stop, "")
        
    for stress in ["{b}"]:
        text = text.replace(stress, ", ")
        
    for markup in [r"\(.+?\)", r"\[.+?\]", r"\{.+?\}"]:
        text = re.sub(markup, "", text)
        
    text = re.sub(r'"(.+?)"', r"\1", text)  # remove quotes
    text = text.replace("''", '"')
    
    return text.strip()