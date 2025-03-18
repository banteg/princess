"""Dialogue and menu choice extraction utilities."""

import re
from pathlib import Path
from .file import walk_script_files, get_game_path
from .characters import extract_characters


def extract_voice_lines(path=None, game_path=None):
    """
    Extract all spoken lines with their corresponding voice file, character, and line.
    
    Args:
        path: Optional specific file path to parse. If None, scans all script files.
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Yields:
        Dictionary containing voice line information
    """
    if game_path is None:
        game_path = get_game_path()
        
    paths = [Path(path)] if path is not None else walk_script_files(game_path)
    characters = list(extract_characters(game_path))
    
    voice_regex = re.compile(
        r'^(?P<indent>\s*)voice\s+"(?P<voice>[^"]+)"', re.MULTILINE
    )
    character_regex = re.compile(
        r"^(?P<indent>\s*)(?P<character>"
        + "|".join(characters)
        + r')\s"(?P<dialogue>[^"]+)(?P<closed>"?)',
        re.MULTILINE,
    )
    label_re = re.compile(r"^\s*label ([a-z]\w+):$")
    
    for path in paths:
        current_label = None
        current_indent = None
        continue_dialogue = None
        
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if label_match := label_re.search(line):
                current_label = label_match.group(1)
                
            if voice_match := voice_regex.search(line):
                current_indent = voice_match.group("indent")
                path_clean = str(path.relative_to(game_path))
                current = {
                    "key": f"{path_clean}:{i:05d}",
                    "path": path_clean,
                    "lineno": i,
                    "label": current_label,
                    "voice": voice_match.group("voice"),
                }
                continue_dialogue = False
            elif char_match := character_regex.search(line):
                if char_match.group("indent") != current_indent:
                    continue
                current.update(
                    {
                        "character": char_match.group("character"),
                        "dialogue": char_match.group("dialogue"),
                    }
                )
                continue_dialogue = char_match.group("closed") != '"'
                if not continue_dialogue:
                    yield current
            elif continue_dialogue:
                match = re.search(r'\s*([^"]+)"', line)
                if match:
                    current["dialogue"] += f" {match.group(1)}"
                    continue_dialogue = False
                    yield current


def extract_choices(path=None, game_path=None):
    """
    Extract menu choices from game scripts.
    
    Args:
        path: Optional specific file path to parse. If None, scans all script files.
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Yields:
        Dictionary containing menu choice information
    """
    if game_path is None:
        game_path = get_game_path()
        
    paths = [Path(path)] if path is not None else walk_script_files(game_path)
    
    menu_re = re.compile(r"(?P<indent>^\s+)menu:")
    option_re = re.compile(r'(?P<indent>^\s+)"(?P<option>[^"]+)"')
    label_re = re.compile(r"^\s*label ([a-z]\w+):$")
    
    for path in paths:
        indent = None
        menu_index = 0
        current_label = None
        
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if label_match := label_re.search(line):
                current_label = label_match.group(1)
                
            if menu := menu_re.search(line):
                indent = len(menu.group("indent"))
                menu_index += 1
                
            if option := option_re.search(line):
                if indent is None or len(option.group("indent")) != indent + 4:
                    continue
                    
                path_clean = str(path.relative_to(game_path))
                yield {
                    "key": f"{path_clean}:{i:05d}",
                    "path": path_clean,
                    "lineno": i,
                    "label": current_label,
                    "menu": menu_index,
                    "option": option.group("option"),
                }


def extract_dialogue_and_choices(game_path=None):
    """
    Extract both dialogue lines and menu choices from game scripts.
    
    Args:
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Yields:
        Dictionary containing either voice lines or menu choices with type indicator
    """
    if game_path is None:
        game_path = get_game_path()
        
    characters = list(extract_characters(game_path))

    # Compile regex patterns
    voice_regex = re.compile(
        r'^(?P<indent>\s*)voice\s+"(?P<voice>[^"]+)"', re.MULTILINE
    )
    character_regex = re.compile(
        r"^(?P<indent>\s*)(?P<character>"
        + "|".join(characters)
        + r')\s"(?P<dialogue>[^"]+)(?P<closed>"?)',
        re.MULTILINE,
    )
    label_re = re.compile(r"^\s*label ([a-z]\w+):$")
    menu_re = re.compile(r"(?P<indent>^\s+)menu:")
    option_re = re.compile(r'(?P<indent>^\s+)"(?P<option>[^"]+)"')

    for path in walk_script_files(game_path):
        path_clean = str(path.relative_to(game_path))
        current_label = None
        current_indent = None
        continue_dialogue = None
        current = None

        menu_indent = None
        menu_index = 0

        for i, line in enumerate(path.read_text().splitlines(), 1):
            # Check for label definitions
            if label_match := label_re.search(line):
                current_label = label_match.group(1)

            # Check for voice lines
            if voice_match := voice_regex.search(line):
                current_indent = voice_match.group("indent")
                current = {
                    "key": f"{path_clean}:{i:05d}",
                    "path": path_clean,
                    "lineno": i,
                    "label": current_label,
                    "voice": voice_match.group("voice"),
                    "type": "voice_line",
                }
                continue_dialogue = False
            elif char_match := character_regex.search(line):
                if char_match.group("indent") != current_indent:
                    continue
                current.update(
                    {
                        "character": char_match.group("character"),
                        "dialogue": char_match.group("dialogue"),
                    }
                )
                continue_dialogue = char_match.group("closed") != '"'
                if not continue_dialogue:
                    yield current
            elif continue_dialogue:
                match = re.search(r'\s*([^"]+)"', line)
                if match:
                    current["dialogue"] += f" {match.group(1)}"
                    continue_dialogue = False
                    yield current

            # Check for menu choices
            if menu_match := menu_re.search(line):
                menu_indent = len(menu_match.group("indent"))
                menu_index += 1
            if option_match := option_re.search(line):
                if (
                    menu_indent is None
                    or len(option_match.group("indent")) != menu_indent + 4
                ):
                    continue
                yield {
                    "key": f"{path_clean}:{i:05d}",
                    "path": path_clean,
                    "lineno": i,
                    "label": current_label,
                    "menu": menu_index,
                    "option": option_match.group("option"),
                    "type": "menu_choice",
                }


def clean_choice_for_tts(choice):
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