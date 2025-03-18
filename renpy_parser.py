import re
from pathlib import Path
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

# List of known characters.
characters = [
    "y",
    "sp",
    "spright",
    "spmid",
    "p",
    "stranger",
    "pmid",
    "wp",
    "swp",
    "n",
    "np",
    "mirror",
    "hero",
    "truth",
    "truthsmall",
    "truthmid",
    "truthside",
    "contrarian",
    "cold",
    "broken",
    "hunted",
    "skeptic",
    "stubborn",
    "smitten",
    "flinching",
    "paranoid",
    "opportunist",
    "cheated",
    "stubcont",
    "parskep",
    "opportunistdragon",
    "herodragon",
    "colddragon",
    "nstub",
    "mound",
    "moundmid",
    "mounds",
]


# Updated cleanup function.
def clean_script(path):
    # Look for lines starting with a known character name followed by spaces and a double quote.
    character_re = re.compile(r"^\s*(" + "|".join(characters) + r")\s+\"")

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


# Updated grammar to handle dialogue lines as: character ws quoted dialogue.
renpy_grammar = Grammar(
    r"""
    script          = statement*
    statement       = (dialogue / voice_line / menu / label_line / other) newline*
    
    # Dialogue: a character name followed by whitespace and a quoted dialogue.
    dialogue        = character ws quoted_dialogue
    character       = ~"(?:y|sp|spright|spmid|p|stranger|pmid|wp|swp|n|np|mirror|hero|truth|truthsmall|truthmid|truthside|contrarian|cold|broken|hunted|skeptic|stubborn|smitten|flinching|paranoid|opportunist|cheated|stubcont|parskep|opportunistdragon|herodragon|colddragon|nstub|mound|moundmid|mounds)"
    # Using a pattern that handles escapes inside the quoted dialogue.
    quoted_dialogue = "\"" ~r'([^"\\]|\\.)*' "\""
    
    # A voice line, e.g., "voice some_voice_file"
    voice_line      = "voice" ws voice_text
    voice_text      = ~".+"
    
    # A menu block.
    menu            = "menu:" ws newline menu_item+
    menu_item       = indent choice_line
    choice_line     = choice_text ":" ws newline (block)?
    choice_text     = "\"" ~r'[^"\n]+' "\""
    block           = (indent block_line newline)+
    block_line      = ~".+"
    
    # A label line, e.g., "label start:"
    label_line      = ~"^\s*label\s.+"
    
    # Catch-all for other lines.
    other           = ~".*"
    
    indent          = "    "
    ws              = ~"[ \t]+"
    newline         = "\n"
    """
)


# Visitor to extract:
# 1. Dialogue lines (with an attached voice line if immediately following)
# 2. Menus paired with the dialogue context (accumulated since the last label).
class RenpyVisitor(NodeVisitor):
    def __init__(self):
        self.current_context = []  # Holds dialogue entries since last label.
        self.dialogues = []  # List of all dialogues.
        self.menus = []  # List of menus with context.
        super().__init__()

    def visit_script(self, node, visited_children):
        return {
            "dialogues": self.dialogues,
            "menus": self.menus,
        }

    def visit_dialogue(self, node, visited_children):
        # Structure: [character, ws, quoted_dialogue]
        char = visited_children[0].text.strip()
        dialogue_raw = visited_children[2].text.strip()
        # Remove the surrounding quotes.
        dialogue_text = (
            dialogue_raw[1:-1]
            if dialogue_raw.startswith('"') and dialogue_raw.endswith('"')
            else dialogue_raw
        )
        entry = {"character": char, "text": dialogue_text, "voice": None}
        self.current_context.append(entry)
        self.dialogues.append(entry)
        return entry

    def visit_voice_line(self, node, visited_children):
        # Structure: ["voice", ws, voice_text]
        voice_txt = visited_children[2].text.strip()
        if self.current_context and self.current_context[-1]["voice"] is None:
            self.current_context[-1]["voice"] = voice_txt
        return voice_txt

    def visit_label_line(self, node, visited_children):
        # Reset context at a label boundary.
        self.current_context = []
        return node.text.strip()

    def visit_menu(self, node, visited_children):
        menu_data = self.extract_menu_choices(node)
        # Capture the dialogue context preceding this menu.
        self.menus.append(
            {
                "context": self.current_context.copy(),
                "menu": menu_data,
            }
        )
        return menu_data

    def extract_menu_choices(self, menu_node):
        choices = []
        for child in menu_node.children:
            if hasattr(child, "expr_name") and child.expr_name == "menu_item":
                choice = self.extract_choice(child)
                if choice:
                    choices.append(choice)
        return choices

    def extract_choice(self, menu_item_node):
        for child in menu_item_node.children:
            if hasattr(child, "expr_name") and child.expr_name == "choice_line":
                choice_text = None
                block_text = None
                for subchild in child.children:
                    if hasattr(subchild, "expr_name"):
                        if subchild.expr_name == "choice_text":
                            choice_text = subchild.text.strip().strip('"')
                        elif subchild.expr_name == "block":
                            block_text = subchild.text.strip()
                return {"choice": choice_text, "block": block_text}
        return None

    def visit_other(self, node, visited_children):
        return None

    def generic_visit(self, node, visited_children):
        return visited_children or node


# Example usage:
if __name__ == "__main__":
    import pprint

    # Clean the script file.
    script_clean = clean_script("script.rpy")
    # Optionally, write out the cleaned script.
    Path("script_clean.rpy").write_text(script_clean)

    # Parse the cleaned script.
    tree = renpy_grammar.parse(script_clean)

    # Visit the parse tree.
    visitor = RenpyVisitor()
    result = visitor.visit(tree)

    pprint.pprint(result)
