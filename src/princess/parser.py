import re
from pathlib import Path

from princess.constants import CHARACTERS


def clean_script(path):
    # Look for lines starting with a known character name followed by spaces and a double quote.
    character_re = re.compile(r"^\s*(" + "|".join(CHARACTERS) + r")\s+\"")

    def clean_inner():
        for line in Path(path).read_text().splitlines():
            if re.search(r"^\s*label\s", line):
                yield line
            elif re.search(r"^\s*menu:", line):
                yield line
            elif re.search(r'^\s*"\{i\}•', line):
                yield line
            elif re.search(r"^\s*voice\s", line):
                yield line
            elif character_re.search(line):
                yield line

    return "\n".join(clean_inner())
