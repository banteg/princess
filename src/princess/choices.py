import re
import networkx as nx
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from rich import print


@dataclass
class Dialogue:
    """Represents a single dialogue line from a character."""

    character: Optional[str] = None
    text: Optional[str] = None
    voice: Optional[str] = None
    label: Optional[str] = None
    node_id: Optional[str] = None
    indent_level: int = 0

    def __str__(self):
        return f'{self.character or "Unknown"}: "{self.text or ""}"' + (
            f" [voice: {self.voice}]" if self.voice else ""
        )


@dataclass
class Choice:
    """Represents a player choice with connections to preceding and following dialogue."""

    text: str
    condition: Optional[str] = None
    node_id: Optional[str] = None
    label_path: List[str] = field(default_factory=list)
    indent_level: int = 0


class RenpyScriptGraph:
    """Represents the Ren'Py script as a directed graph."""

    def __init__(self, characters):
        self.characters = characters
        self.character_re = re.compile(r"^\s*(" + "|".join(characters) + r")\s+\"(.+)\"")
        self.label_re = re.compile(r"^\s*label\s+(\w+):")
        self.menu_re = re.compile(r"^\s*menu:")
        self.choice_re = re.compile(r'^\s+"(\{i\}•\s*.*?\{/i\}|\[\[.*?\]|.*?)"(\s+if\s+(.+?))?:')
        self.voice_re = re.compile(r'^\s*voice\s+"([^"]+)"')

        # Create directed graph to represent the script
        self.graph = nx.DiGraph()

        # Tracking state
        self.current_label = None
        self.label_stack = []
        self.current_node_id = 0
        self.choices = []
        self.current_voice = None
        self.menu_stack = []
        self.branch_stack = []
        self.last_dialogue_node = None

    def get_next_node_id(self):
        """Generate a unique ID for each node in the graph."""
        self.current_node_id += 1
        return f"node_{self.current_node_id}"

    def get_indent_level(self, line):
        """Calculate indentation level of a line."""
        return len(line) - len(line.lstrip())

    def clean_script(self, path):
        """Filter relevant lines from the script."""
        lines = []
        for line in Path(path).read_text().splitlines():
            if (
                self.label_re.search(line)
                or self.menu_re.search(line)
                or self.choice_re.search(line)
                or self.voice_re.search(line)
                or self.character_re.search(line)
            ):
                lines.append(line)
        return lines

    def parse_script(self, path):
        """Parse the script into a dialogue graph."""
        lines = self.clean_script(path)
        line_indents = [self.get_indent_level(line) for line in lines]

        i = 0
        while i < len(lines):
            line = lines[i]
            indent = line_indents[i]

            # Pop branch context when indent decreases
            while self.branch_stack and indent <= self.branch_stack[-1][1]:
                self.branch_stack.pop()

            # New label
            if label_match := self.label_re.search(line):
                label_name = label_match.group(1)
                self.current_label = label_name
                self.label_stack = [label_name]

                # Create a label node
                node_id = self.get_next_node_id()
                self.graph.add_node(node_id, type="label", label=label_name)

                # Connect to previous dialogue if we have one
                if self.last_dialogue_node:
                    self.graph.add_edge(self.last_dialogue_node, node_id)

                self.last_dialogue_node = node_id
                i += 1
                continue

            # Voice line
            if voice_match := self.voice_re.search(line):
                self.current_voice = voice_match.group(1)
                i += 1
                continue

            # Character dialogue
            if character_match := self.character_re.search(line):
                character, text = character_match.group(1), character_match.group(2)

                # Create dialogue node
                node_id = self.get_next_node_id()
                dialogue = Dialogue(
                    character=character,
                    text=text,
                    voice=self.current_voice,
                    label=self.current_label,
                    node_id=node_id,
                    indent_level=indent,
                )

                self.graph.add_node(node_id, type="dialogue", data=dialogue)

                # Connect to previous dialogue or branch
                if self.branch_stack:
                    for branch_id, _ in self.branch_stack:
                        self.graph.add_edge(branch_id, node_id)
                elif self.last_dialogue_node:
                    self.graph.add_edge(self.last_dialogue_node, node_id)

                self.last_dialogue_node = node_id
                self.current_voice = None
                i += 1
                continue

            # Menu (choice set)
            if self.menu_re.search(line):
                # Create a menu node
                node_id = self.get_next_node_id()
                self.graph.add_node(node_id, type="menu")

                # Connect to previous dialogue
                if self.last_dialogue_node:
                    self.graph.add_edge(self.last_dialogue_node, node_id)

                # Push menu to stack
                self.menu_stack.append((node_id, indent))
                i += 1
                continue

            # Choice
            if choice_match := self.choice_re.search(line):
                choice_text = choice_match.group(1)
                condition = choice_match.group(3) if choice_match.group(2) else None

                # Clean choice text
                choice_text = re.sub(r"\{[^}]+\}", "", choice_text)
                choice_text = re.sub(r"\[\[|\]\]", "", choice_text)

                # Create choice node
                node_id = self.get_next_node_id()
                choice = Choice(
                    text=choice_text,
                    condition=condition,
                    node_id=node_id,
                    label_path=self.label_stack.copy(),
                    indent_level=indent,
                )

                self.graph.add_node(node_id, type="choice", data=choice)
                self.choices.append(choice)

                # Connect choice to its menu
                if self.menu_stack:
                    menu_id, _ = self.menu_stack[-1]
                    self.graph.add_edge(menu_id, node_id)

                # Add choice to branch stack
                self.branch_stack.append((node_id, indent))

                i += 1
                continue

            i += 1

        return self.extract_choice_contexts()

    def extract_choice_contexts(self):
        """Extract the full dialogue context for each choice."""
        result = []

        for choice in self.choices:
            # Extract context by navigating backwards in the graph
            context_before = self.get_context_before(choice.node_id)
            context_after = self.get_context_after(choice.node_id)

            # Combine contexts and format result
            result.append(
                {"choice": choice, "context_before": context_before, "context_after": context_after}
            )

        return result

    def get_context_before(self, choice_node_id, max_depth=100, visited=None):
        """Extract dialogue context coming before a choice."""
        if visited is None:
            visited = set()

        if max_depth <= 0 or choice_node_id in visited:
            return []

        visited.add(choice_node_id)
        context = []

        # Get predecessors in the graph
        for pred in self.graph.predecessors(choice_node_id):
            node_data = self.graph.nodes[pred]
            node_type = node_data.get("type")

            if node_type == "dialogue":
                # Add dialogue to context
                context.append(node_data.get("data"))

            # Recursively get context from predecessors
            pred_context = self.get_context_before(pred, max_depth - 1, visited)
            context.extend(pred_context)

        return context

    def get_context_after(self, choice_node_id, max_depth=100, visited=None):
        """Extract dialogue context following a choice."""
        if visited is None:
            visited = set()

        if max_depth <= 0 or choice_node_id in visited:
            return []

        visited.add(choice_node_id)
        context = []

        # Get successors in the graph
        for succ in self.graph.successors(choice_node_id):
            node_data = self.graph.nodes[succ]
            node_type = node_data.get("type")

            if node_type == "dialogue":
                # Add dialogue to context
                context.append(node_data.get("data"))

            # Recursively get context from successors
            succ_context = self.get_context_after(succ, max_depth - 1, visited)
            context.extend(succ_context)

        return context


def extract_script_structure(script_path, characters):
    """Process a Ren'Py script and extract its dialogue structure."""
    parser = RenpyScriptGraph(characters)
    choice_contexts = parser.parse_script(script_path)

    # Print formatted results
    for i, item in enumerate(choice_contexts, 1):
        choice = item["choice"]
        label_path = ".".join(choice.label_path)

        print(f"\nChoice {i} in {label_path}:")
        print(f"  Text: {choice.text}")
        if choice.condition:
            print(f"  Condition: {choice.condition}")

        print("  Dialogue Context Before:")
        for dialogue in sorted(item["context_before"], key=lambda d: d.node_id):
            print(f"    {dialogue}")

        print("  Dialogue Context After (response to this choice):")
        for dialogue in sorted(item["context_after"], key=lambda d: d.node_id):
            print(f"    {dialogue}")

    print(f"\nTotal choices extracted: {len(choice_contexts)}")
    return choice_contexts, parser.graph


if __name__ == "__main__":
    from princess.constants import CHARACTERS

    print("=" * 120)
    extract_script_structure("script.rpy", CHARACTERS)
