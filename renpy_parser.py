from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from pathlib import Path
import pprint

grammar = Grammar(r"""
script          = statement*
statement       = ws (label / menu / voice / dialogue / jump / other_stmt) ws

label           = "label" ws identifier ":" statement*
menu            = "menu" ":" choice+
choice          = ws quoted_text statement*

voice           = "voice" ws quoted_text ws
dialogue        = identifier ws quoted_text ws
jump            = "jump" ws identifier ws

identifier      = ~"[a-zA-Z_][a-zA-Z0-9_]*"
quoted_text     = '"' text '"'
text            = ~"[^\"\n]+"

other_stmt      = ~"[^\n]+" ws  # catch-all for unimportant lines

ws              = ~"[ \t\r\n]*"
""")


class ChoiceContextVisitor(NodeVisitor):
    def __init__(self):
        self.choices = []
        self.current_label = None
        self.current_context = []

    def visit_script(self, node, visited_children):
        return self.choices

    def visit_statement(self, node, visited_children):
        _, stmt, _ = visited_children
        return stmt

    def visit_label(self, node, visited_children):
        _, _, label_name, _, statements = visited_children
        self.current_label = label_name
        self.current_context = []

        for stmt in statements:
            if isinstance(stmt, dict) and stmt["type"] == "menu":
                for choice in stmt["choices"]:
                    self.choices.append(
                        {
                            "label": self.current_label,
                            "choice": choice["text"],
                            "context": self.current_context.copy(),
                        }
                    )
            elif isinstance(stmt, dict) and stmt["type"] in ("dialogue", "voice"):
                self.current_context.append(stmt)

        self.current_label = None
        self.current_context = []

    def visit_menu(self, node, visited_children):
        _, _, choices = visited_children
        return {"type": "menu", "choices": choices}

    def visit_choice(self, node, visited_children):
        _, text, statements = visited_children
        return {"text": text, "statements": statements}

    def visit_voice(self, node, visited_children):
        _, _, path, _ = visited_children
        return {"type": "voice", "path": path}

    def visit_dialogue(self, node, visited_children):
        speaker, _, text, _ = visited_children
        return {"type": "dialogue", "speaker": speaker, "text": text}

    def visit_jump(self, node, visited_children):
        _, _, target, _ = visited_children
        return {"type": "jump", "target": target}

    def visit_other_stmt(self, node, visited_children):
        return None  # Explicitly ignore all other statements

    def visit_identifier(self, node, _):
        return node.text.strip()

    def visit_quoted_text(self, node, visited_children):
        _, text, _ = visited_children
        return text

    def visit_text(self, node, _):
        return node.text.strip()

    def visit_ws(self, node, _):
        pass

    def generic_visit(self, node, visited_children):
        result = []
        for child in visited_children:
            if isinstance(child, list):
                result.extend(child)
            elif isinstance(child, dict):
                result.append(child)
        return result or None


example_script = """
label splashscreen:
    voice "audio/voices/ch1/woods/narrator/script_n_1.flac"
    n "You're on a path in the woods."
    menu:
        "{i}• Why do I need to slay her?{/i}"
        voice "audio/voices/ch1/woods/narrator/script_n_3.flac"
        n "I just told you."
        jump forest_dialogue
"""


# parsed_tree = grammar.parse(Path('script.rpy').read_text())
parsed_tree = grammar.parse(example_script)
visitor = ChoiceContextVisitor()
visitor.visit(parsed_tree)
pprint.pprint(visitor.choices, width=120)
