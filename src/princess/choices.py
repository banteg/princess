import re
from pathlib import Path
from princess.constants import CHARACTERS
from rich import print


def extract_choices_with_context(path):
    label_re = re.compile(r"^\s*label\s+(\w+):")
    character_re = re.compile(r"^\s*(" + "|".join(CHARACTERS) + r")\s+\"(.+)\"")
    menu_re = re.compile(r"^\s*menu:")
    choice_re = re.compile(r"^\s+\"(.+?)\"")
    voice_re = re.compile(r'^\s*voice\s+"([^"]+)"')

    current_label = None

    for line in Path(path).read_text().splitlines():
        print(f"[dim]{line}[/dim]")
        if label_match := label_re.search(line):
            current_label = label_match.group(1)
            print(f"new label: {current_label}")
        elif character_match := character_re.search(line):
            print(f"new character: {character_match.group(1)}")
        elif menu_match := menu_re.search(line):
            print(f"new menu: {menu_match.group(1)}")
        elif choice_match := choice_re.search(line):
            print(f"new choice: {choice_match.group(1)}")
        elif voice_match := voice_re.search(line):
            print(f"new voice: {voice_match.group(1)}")


if __name__ == "__main__":
    extract_choices_with_context("script.rpy")
