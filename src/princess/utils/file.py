"""File-related utility functions."""

import os
from pathlib import Path


def get_game_path():
    """Get the game path from environment variable."""
    return Path(os.environ["GAME_PATH"])


def walk_script_files(game_path=None):
    """
    Iterate over all script files.

    Args:
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.

    Yields:
        Path objects for each script file
    """
    if game_path is None:
        game_path = get_game_path()

    for path in game_path.rglob("*.rpy"):
        yield path
