import re
from pathlib import Path
from princess.game import walk_script_files


def extract_characters(game_path=None):
    CHARACTER_RE = re.compile(r"^define (.*?) = Character\(")

    def extract_inner():
        for path in walk_script_files(game_path):
            for line in Path(path).read_text().splitlines():
                if match := CHARACTER_RE.search(line.lstrip()):
                    yield match.group(1)

    return list(extract_inner())


if __name__ == "__main__":
    print(extract_characters())
