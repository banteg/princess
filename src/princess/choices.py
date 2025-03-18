import re
import json
import networkx as nx
from pathlib import Path
from dataclasses import dataclass, field, asdict
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

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "type": "dialogue",
            "character": self.character,
            "text": self.text,
            "voice": self.voice,
            "label": self.label,
            "node_id": self.node_id,
            "indent_level": self.indent_level,
        }


@dataclass
class Choice:
    """Represents a player choice with connections to preceding and following dialogue."""

    text: str
    condition: Optional[str] = None
    node_id: Optional[str] = None
    label_path: List[str] = field(default_factory=list)
    indent_level: int = 0

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "type": "choice",
            "text": self.text,
            "condition": self.condition,
            "node_id": self.node_id,
            "label_path": self.label_path,
            "indent_level": self.indent_level,
        }


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

    def export_graph_to_json(self, output_path):
        """Export the graph to a JSON file for external analysis."""
        # Create a serializable representation of the graph
        serialized_graph = {"nodes": [], "edges": []}

        # Convert nodes to dictionaries
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type")

            node_info = {
                "id": node_id,
                "type": node_type,
            }

            # Handle different node types
            if node_type == "dialogue":
                dialogue = node_data.get("data")
                node_info.update(dialogue.to_dict())
            elif node_type == "choice":
                choice = node_data.get("data")
                node_info.update(choice.to_dict())
            elif node_type == "label":
                node_info["label"] = node_data.get("label")

            serialized_graph["nodes"].append(node_info)

        # Convert edges to list of pairs
        for source, target in self.graph.edges:
            serialized_graph["edges"].append({"source": source, "target": target})

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized_graph, f, indent=2)

        print(f"Graph exported to {output_path}")
        return serialized_graph

    def export_graphviz(self, output_path):
        """Export the graph in DOT format for visualization with Graphviz."""
        # Create a copy of the graph with enhanced attributes for visualization
        viz_graph = nx.DiGraph()

        # Add nodes with visualization attributes
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type")

            attrs = {
                "label": node_id,
                "shape": "ellipse",
            }

            if node_type == "dialogue":
                dialogue = node_data.get("data")
                attrs["label"] = (
                    f"{dialogue.character}: {dialogue.text[:30]}..."
                    if dialogue.text and len(dialogue.text) > 30
                    else f"{dialogue.character}: {dialogue.text}"
                )
                attrs["shape"] = "box"
                attrs["color"] = "blue"
            elif node_type == "choice":
                choice = node_data.get("data")
                attrs["label"] = (
                    f"Choice: {choice.text[:30]}..."
                    if choice.text and len(choice.text) > 30
                    else f"Choice: {choice.text}"
                )
                attrs["shape"] = "diamond"
                attrs["color"] = "green"
            elif node_type == "label":
                attrs["label"] = f"Label: {node_data.get('label')}"
                attrs["shape"] = "hexagon"
                attrs["color"] = "red"
            elif node_type == "menu":
                attrs["label"] = "Menu"
                attrs["shape"] = "octagon"
                attrs["color"] = "purple"

            viz_graph.add_node(node_id, **attrs)

        # Add edges
        for source, target in self.graph.edges:
            viz_graph.add_edge(source, target)

        # Write to DOT file
        nx.drawing.nx_pydot.write_dot(viz_graph, output_path)
        print(f"Graph visualization exported to {output_path}")

        # Suggest visualization command
        print("To visualize the graph, you can use the following command:")
        print(f"  dot -Tpng {output_path} -o {output_path.replace('.dot', '.png')}")
        print("Or open the DOT file with a Graphviz viewer like Gephi or graphviz-online.com")


def export_to_cytoscape(graph, output_path):
    """
    Export the graph to a Cytoscape-compatible JSON format.

    Args:
        graph: The NetworkX directed graph
        output_path: Path to save the Cytoscape JSON file
    """
    import json

    # Create the Cytoscape JSON structure
    cytoscape_data = {"elements": {"nodes": [], "edges": []}}

    # Convert nodes to Cytoscape format
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id]
        node_type = node_data.get("type")

        # Base node data
        cy_node = {"data": {"id": node_id, "type": node_type}}

        # Handle different node types with specific data and styling
        if node_type == "dialogue":
            dialogue = node_data.get("data")
            if dialogue:
                cy_node["data"].update(
                    {
                        "character": dialogue.character,
                        "text": dialogue.text,
                        "voice": dialogue.voice,
                        "label": dialogue.label,
                        "indent_level": dialogue.indent_level,
                    }
                )
                # Add display label for visualization
                cy_node["data"]["name"] = (
                    f"{dialogue.character}: {dialogue.text[:50]}..."
                    if dialogue.text and len(dialogue.text) > 50
                    else f"{dialogue.character}: {dialogue.text or ''}"
                )
                # Add visual styling
                cy_node["classes"] = "dialogue"

        elif node_type == "choice":
            choice = node_data.get("data")
            if choice:
                cy_node["data"].update(
                    {
                        "text": choice.text,
                        "condition": choice.condition,
                        "label_path": choice.label_path,
                        "indent_level": choice.indent_level,
                    }
                )
                # Add display label for visualization
                cy_node["data"]["name"] = (
                    f"Choice: {choice.text[:50]}..."
                    if choice.text and len(choice.text) > 50
                    else f"Choice: {choice.text}"
                )
                # Add visual styling
                cy_node["classes"] = "choice"

        elif node_type == "label":
            label_name = node_data.get("label")
            cy_node["data"]["name"] = f"Label: {label_name}"
            cy_node["data"]["label_name"] = label_name
            cy_node["classes"] = "label"

        elif node_type == "menu":
            cy_node["data"]["name"] = "Menu"
            cy_node["classes"] = "menu"

        cytoscape_data["elements"]["nodes"].append(cy_node)

    # Convert edges to Cytoscape format
    for i, (source, target) in enumerate(graph.edges):
        cy_edge = {"data": {"id": f"edge_{i}", "source": source, "target": target}}
        cytoscape_data["elements"]["edges"].append(cy_edge)

    # Add recommended Cytoscape style
    cytoscape_data["style"] = [
        {
            "selector": "node",
            "style": {
                "label": "data(name)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": "12px",
                "width": "label",
                "height": "label",
                "padding": "10px",
                "text-wrap": "wrap",
                "text-max-width": "200px",
            },
        },
        {"selector": "edge", "style": {"curve-style": "bezier", "target-arrow-shape": "triangle"}},
        {
            "selector": ".dialogue",
            "style": {"background-color": "#7BB0FF", "shape": "round-rectangle"},
        },
        {"selector": ".choice", "style": {"background-color": "#A9FF7B", "shape": "diamond"}},
        {"selector": ".label", "style": {"background-color": "#FF7B7B", "shape": "hexagon"}},
        {"selector": ".menu", "style": {"background-color": "#D17BFF", "shape": "octagon"}},
    ]

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cytoscape_data, f, indent=2)

    print(f"Cytoscape-compatible graph exported to {output_path}")
    return cytoscape_data


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
    import json
    import os

    # Extract just the filename from the path
    filename = os.path.basename(script_path)

    result = []
    for item in choice_contexts:
        choice = item["choice"]

        # Get context before (up to 3 items)
        context_before = item["context_before"]
        # Sort by node_id to maintain proper order
        context_before = sorted(context_before, key=lambda d: d.node_id)
        # Take the last 3 items
        context_before = context_before[-3:] if len(context_before) > 3 else context_before

        # Get context after (up to 3 items)
        context_after = item["context_after"]
        # Sort by node_id to maintain proper order
        context_after = sorted(context_after, key=lambda d: d.node_id)
        # Take the first 3 items
        context_after = context_after[:3] if len(context_after) > 3 else context_after

        # Format context items as strings with metadata
        formatted_context_before = []
        for dialogue in context_before:
            metadata = {
                "character": dialogue.character,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            }
            formatted_context_before.append({"text": str(dialogue), "metadata": metadata})

        formatted_context_after = []
        for dialogue in context_after:
            metadata = {
                "character": dialogue.character,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            }
            formatted_context_after.append({"text": str(dialogue), "metadata": metadata})

        # Get the current label from the choice
        current_label = choice.label_path[-1] if choice.label_path else None

        # Add entry to result list
        result.append(
            {
                "filename": filename,
                "lineno": -1,  # Placeholder since we don't track line numbers in the current implementation
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
    import json
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

        # Format context items as strings with metadata
        formatted_context_before = []
        for dialogue in context_before:
            metadata = {
                "character": dialogue.character,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            }
            formatted_context_before.append({"text": str(dialogue), "metadata": metadata})

        formatted_context_after = []
        for dialogue in context_after:
            metadata = {
                "character": dialogue.character,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            }
            formatted_context_after.append({"text": str(dialogue), "metadata": metadata})

        # Get the current label from the choice
        current_label = choice.label_path[-1] if choice.label_path else None

        # Add entry to result list
        result.append(
            {
                "filename": filename,
                "lineno": -1,  # Placeholder since we don't track line numbers in the current implementation
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
    import json
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
                "lineno": -1,  # Placeholder since we don't track line numbers in the current implementation
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


# Update the extract_script_structure function to include the new export option
def extract_script_structure(
    script_path,
    characters,
    export_json=None,
    export_dot=None,
    export_cytoscape=None,
    export_specific_json=None,
):
    """Process a Ren'Py script and extract its dialogue structure."""
    parser = RenpyScriptGraph(characters)
    choice_contexts = parser.parse_script(script_path)

    # Print formatted results with enhanced display
    for i, item in enumerate(choice_contexts, 1):
        choice = item["choice"]
        label_path = ".".join(choice.label_path)

        print(f"\n{'-' * 80}")
        print(f"Choice {i} in {label_path}:")

        # Display context before
        context_before = sorted(item["context_before"], key=lambda d: d.node_id)
        if context_before:
            print("\nContext Before:")
            for dialogue in context_before[-3:]:  # Last 3 lines of context
                print(
                    f'  {dialogue.character or "Unknown"}: "{dialogue.text or ""}"'
                    + (f" [voice: {dialogue.voice}]" if dialogue.voice else "")
                )

        # Display choice in bold yellow
        from rich import print as rich_print

        rich_print(f"\n[bold yellow]Choice: {choice.text}[/bold yellow]")
        if choice.condition:
            print(f"Condition: {choice.condition}")

        # Display context after
        context_after = sorted(item["context_after"], key=lambda d: d.node_id)
        if context_after:
            print("\nContext After:")
            for dialogue in context_after[:3]:  # First 3 lines of context
                print(
                    f'  {dialogue.character or "Unknown"}: "{dialogue.text or ""}"'
                    + (f" [voice: {dialogue.voice}]" if dialogue.voice else "")
                )

        print(f"{'-' * 80}")

    print(f"\nTotal choices extracted: {len(choice_contexts)}")

    # Export the graph if requested
    if export_json:
        parser.export_graph_to_json(export_json)

    if export_dot:
        parser.export_graphviz(export_dot)

    if export_cytoscape:
        export_to_cytoscape(parser.graph, export_cytoscape)

    # Add the specific JSON export
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
        export_json="script_graph.json",
        export_dot="script_graph.dot",
        export_cytoscape="script_cytoscape.json",
        export_specific_json="script_specific.json",  # New parameter for specific JSON format
    )
