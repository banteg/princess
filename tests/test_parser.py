import pytest
from princess.parser import parse_script
from princess.game import walk_script_files


SCRIPT_FILES = list(walk_script_files())


@pytest.mark.parametrize("script_file", SCRIPT_FILES)
def test_parse_game_scripts(script_file):
    parse_script(script_file)
