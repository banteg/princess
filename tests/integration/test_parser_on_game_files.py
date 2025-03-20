import pytest
from princess.parser import parse_script, extract_choices
from princess.game import walk_script_files


SCRIPT_FILES = list(walk_script_files())


@pytest.mark.parametrize("script_file", SCRIPT_FILES)
def test_parse_script(script_file):
    parse_script(script_file)


@pytest.mark.parametrize("script_file", SCRIPT_FILES)
def test_extract_choices(script_file):
    tree = parse_script(script_file)
    extract_choices(tree)
