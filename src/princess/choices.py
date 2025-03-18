import re
import json
import networkx as nx
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
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
    line_number: int = -1


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
        """Filter relevant lines from the script and track their original line numbers.
        
        Returns:
            Tuple of (lines, line_numbers) where line_numbers contains the original
            line number in the source file for each filtered line.
        """
        lines = []
        line_numbers = []
        
        for i, line in enumerate(Path(path).read_text().splitlines(), 1):
            if (
                self.label_re.search(line)
                or self.menu_re.search(line)
                or self.choice_re.search(line)
                or self.voice_re.search(line)
                or self.character_re.search(line)
            ):
                lines.append(line)
                line_numbers.append(i)
                
        return lines, line_numbers

    def parse_script(self, path):
        """Parse the script into a dialogue graph."""
        lines, line_numbers = self.clean_script(path)
        line_indents = [self.get_indent_level(line) for line in lines]

        i = 0
        while i < len(lines):
            line = lines[i]
            indent = line_indents[i]
            original_line_number = line_numbers[i]

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

                # Create choice node
                node_id = self.get_next_node_id()
                choice = Choice(
                    text=choice_text,
                    condition=condition,
                    node_id=node_id,
                    label_path=self.label_stack.copy(),
                    indent_level=indent,
                    line_number=original_line_number,
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


def export_to_specific_json(choice_contexts, script_path, output_path):
    """
    Export the dialogue choices and their contexts to a specific JSON format.

    Args:
        choice_contexts: List of choice contexts extracted from the script
        script_path: Path to the original script file (for filename)
        output_path: Path to save the JSON file

    Format:
    [
        {
            "filename": str,
            "lineno": int,  # We'll use a placeholder as line numbers aren't tracked
            "current_label": str,
            "choice_text": str,
            "context_before": list[str],  # 3 lines of context before
            "context_after": list[str]    # 3 lines of context after
        },
        ...
    ]
    """
    import os

    # Extract just the filename from the path
    filename = os.path.basename(script_path)

    result = []
    for item in choice_contexts:
        choice = item["choice"]

        # Get context before
        context_before = item["context_before"]
        # Filter out lines starting with "Note: You can skip" or containing "{fast}"
        context_before = [
            d
            for d in context_before
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        # Sort by node_id to maintain proper order
        context_before = sorted(context_before, key=lambda d: d.node_id)
        # Take the last 3 items
        context_before = context_before[-3:] if len(context_before) > 3 else context_before

        # Get context after
        context_after = item["context_after"]
        # Filter out lines starting with "Note: You can skip" or containing "{fast}"
        context_after = [
            d
            for d in context_after
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        # Sort by node_id to maintain proper order
        context_after = sorted(context_after, key=lambda d: d.node_id)
        # Take the first 3 items
        context_after = context_after[:3] if len(context_after) > 3 else context_after

        # Format context items with separate fields instead of combined string
        formatted_context_before = []
        for dialogue in context_before:
            formatted_context_before.append(
                {
                    "character": dialogue.character,
                    "text": dialogue.text,
                    "voice": dialogue.voice,
                    "label": dialogue.label,
                    "node_id": dialogue.node_id,
                }
            )

        formatted_context_after = []
        for dialogue in context_after:
            formatted_context_after.append(
                {
                    "character": dialogue.character,
                    "text": dialogue.text,
                    "voice": dialogue.voice,
                    "label": dialogue.label,
                    "node_id": dialogue.node_id,
                }
            )

        # Get the current label from the choice
        current_label = choice.label_path[-1] if choice.label_path else None

        # Add entry to result list
        result.append(
            {
                "filename": filename,
                "lineno": choice.line_number,  # Use the actual line number from the choice
                "current_label": current_label,
                "choice_text": choice.text,
                "context_before": formatted_context_before,
                "context_after": formatted_context_after,
            }
        )

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Specific format JSON exported to {output_path}")
    return result


# Update the extract_script_structure function to include only the specific JSON export
def extract_script_structure(
    script_path,
    characters,
    export_specific_json=None,
):
    """Process a Ren'Py script and extract its dialogue structure."""
    parser = RenpyScriptGraph(characters)
    choice_contexts = parser.parse_script(script_path)

    # Print formatted results with enhanced display (console visualization)
    for i, item in enumerate(choice_contexts, 1):
        choice = item["choice"]
        label_path = ".".join(choice.label_path)

        print(f"\n{'-' * 80}")
        print(f"Choice {i} in {label_path}:")

        # Display context before
        context_before = sorted(item["context_before"], key=lambda d: d.node_id)
        # Filter out "Note: You can skip" and "{fast}" lines
        context_before = [
            d for d in context_before 
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        
        if context_before:
            print("\nContext Before:")
            for dialogue in context_before[-3:]:  # Last 3 lines of context
                print(
                    f'{dialogue.character or "Unknown"}: "{dialogue.text or ""}"'
                    + (f" [voice: {dialogue.voice}]" if dialogue.voice else "")
                )

        # Display choice in bold yellow
        from rich import print as rich_print

        rich_print(f"\n[bold yellow]Choice: {choice.text}[/bold yellow]")
        if choice.condition:
            print(f"Condition: {choice.condition}")

        # Display context after
        context_after = sorted(item["context_after"], key=lambda d: d.node_id)
        # Filter out "Note: You can skip" and "{fast}" lines
        context_after = [
            d for d in context_after 
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        
        if context_after:
            print("\nContext After:")
            for dialogue in context_after[:3]:  # First 3 lines of context
                print(
                    f'{dialogue.character or "Unknown"}: "{dialogue.text or ""}"'
                    + (f" [voice: {dialogue.voice}]" if dialogue.voice else "")
                )

        print(f"{'-' * 80}")

    print(f"\nTotal choices extracted: {len(choice_contexts)}")

    # Only export the specific JSON format
    if export_specific_json:
        export_to_specific_json(choice_contexts, script_path, export_specific_json)

    return choice_contexts, parser.graph


# Example usage:
if __name__ == "__main__":
    from princess.constants import CHARACTERS

    print("=" * 120)

    # Extract and export the script structure
    script_path = "script.rpy"
    choices, graph = extract_script_structure(
        script_path,
        CHARACTERS,
        export_specific_json="script_specific.json",  # Only keep the specific JSON format export
    )