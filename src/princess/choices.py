from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
import re
from pathlib import Path


@dataclass
class Dialogue:
    character: Optional[str] = None
    text: Optional[str] = None
    voice: Optional[str] = None

    def __str__(self):
        return f'{self.character}: "{self.text}"'


@dataclass
class Choice:
    text: str
    content: List[Any] = field(default_factory=list)

    def __str__(self):
        return f'Choice: "{self.text}"'


@dataclass
class Menu:
    choices: List[Choice] = field(default_factory=list)

    def __str__(self):
        return f"Menu with {len(self.choices)} choices"


@dataclass
class Label:
    name: str
    content: List[Any] = field(default_factory=list)

    def __str__(self):
        return f"Label: {self.name}"


class RenpyParser:
    def __init__(self, characters):
        self.characters = characters
        self.character_re = re.compile(r"^\s*(" + "|".join(characters) + r")\s+\"(.+)\"")
        self.label_re = re.compile(r"^\s*label\s+(\w+):")
        self.menu_re = re.compile(r"^\s*menu:")
        self.choice_re = re.compile(r'^\s+"\{i\}•\s*(.+?)\{/i\}"')
        self.voice_re = re.compile(r'^\s*voice\s+"([^"]+)"')
        self.indent_re = re.compile(r"^(\s*)")

    def get_indent_level(self, line):
        match = self.indent_re.match(line)
        return len(match.group(1)) if match else 0

    def clean_script(self, path):
        cleaned_lines = []
        for line in Path(path).read_text().splitlines():
            if (
                self.label_re.search(line)
                or self.menu_re.search(line)
                or self.choice_re.search(line)
                or self.voice_re.search(line)
                or self.character_re.search(line)
            ):
                cleaned_lines.append(line)
        return cleaned_lines

    def parse_script(self, path):
        lines = self.clean_script(path)
        labels = {}

        i = 0
        while i < len(lines):
            if label_match := self.label_re.search(lines[i]):
                label_name = label_match.group(1)
                label = Label(name=label_name)
                labels[label_name] = label

                i, label.content = self.parse_block(lines, i + 1, 0)
            else:
                i += 1

        return labels

    def parse_block(self, lines, start_idx, parent_indent):
        content = []
        current_dialogue = None
        i = start_idx

        while i < len(lines):
            current_indent = self.get_indent_level(lines[i])

            # If we're at a shallower indent than our parent, we're done with this block
            if current_indent <= parent_indent and i > start_idx:
                break

            # Check for voice line
            if voice_match := self.voice_re.search(lines[i]):
                voice_file = voice_match.group(1)
                current_dialogue = Dialogue(voice=voice_file)
                content.append(current_dialogue)
                i += 1
                continue

            # Check for character dialogue
            if character_match := self.character_re.search(lines[i]):
                character, text = character_match.group(1), character_match.group(2)
                if current_dialogue and not current_dialogue.character:
                    current_dialogue.character = character
                    current_dialogue.text = text
                else:
                    current_dialogue = Dialogue(character=character, text=text)
                    content.append(current_dialogue)
                i += 1
                continue

            # Check for menu
            if self.menu_re.search(lines[i]):
                menu = Menu()
                content.append(menu)
                i, menu.choices = self.parse_menu(lines, i + 1, current_indent)
                continue

            i += 1

        return i, content

    def parse_menu(self, lines, start_idx, parent_indent):
        choices = []
        i = start_idx

        while i < len(lines):
            current_indent = self.get_indent_level(lines[i])

            # If we're at a shallower indent than our parent, we're done with this menu
            if current_indent <= parent_indent:
                break

            # Check for choice
            if choice_match := self.choice_re.search(lines[i]):
                choice_text = choice_match.group(1)
                choice = Choice(text=choice_text)
                choices.append(choice)

                # Parse the content of this choice
                choice_indent = current_indent
                i += 1
                i, choice.content = self.parse_block(lines, i, choice_indent)
                continue

            i += 1

        return i, choices


def extract_choices_with_full_context(labels):
    results = []

    for label in labels.values():
        extract_choices_from_block(label.content, [], results, label_path=label.name)

    return results


def extract_choices_from_block(block, dialogue_context, results, label_path):
    for item in block:
        if isinstance(item, Dialogue):
            dialogue_context.append(item)
        elif isinstance(item, Menu):
            for choice in item.choices:
                # Create a copy of the dialogue context for this choice
                choice_context = dialogue_context.copy()

                # Add this choice and its full context to results
                results.append(
                    {
                        "label_path": label_path,
                        "choice_text": choice.text,
                        "dialogue_context": choice_context,
                    }
                )

                # Recursively process the content of this choice
                extract_choices_from_block(
                    choice.content,
                    dialogue_context + [Dialogue(None, f"CHOICE: {choice.text}")],
                    results,
                    label_path,
                )


def main():
    from princess.constants import CHARACTERS

    parser = RenpyParser(CHARACTERS)
    labels = parser.parse_script("script.rpy")

    choices_with_context = extract_choices_with_full_context(labels)

    for i, choice_data in enumerate(choices_with_context):
        print(f"\nChoice {i + 1} in {choice_data['label_path']}:")
        print(f"  Text: {choice_data['choice_text']}")
        print("  Dialogue Context:")
        for dialogue in choice_data["dialogue_context"]:
            print(f"    {dialogue}")


if __name__ == "__main__":
    main()
