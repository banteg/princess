"""Character extraction utilities."""

import re
from pathlib import Path
from .file import walk_script_files


def extract_characters(game_path=None):
    """
    Extract all character identifiers from game scripts.
    
    Args:
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Yields:
        Character identifiers
    """
    CHARACTER_RE = re.compile(r"^define (.*?) = Character\(")
    
    for path in walk_script_files(game_path):
        for line in Path(path).read_text().splitlines():
            if match := CHARACTER_RE.search(line.lstrip()):
                yield match.group(1)