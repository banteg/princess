import os
from pathlib import Path


def get_game_path():
    return Path(os.environ["GAME_PATH"])


def walk_script_files(game_path=None):
    if game_path is None:
        game_path = get_game_path()

    yield from game_path.rglob("*.rpy")
