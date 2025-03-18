"""Navigation and script flow utilities."""

import re
from collections import defaultdict
import networkx as nx
from .file import walk_script_files, get_game_path


def find_labels_and_jumps(game_path=None):
    """
    Find all labels and jumps in game scripts.
    
    Args:
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Yields:
        Dictionary containing information about jumps between labels
    """
    if game_path is None:
        game_path = get_game_path()
        
    # first collect all labels metadata
    label_re = re.compile(r"^\s*label ([a-z]\w+):$")
    jump_re = re.compile(r"^\s*jump (\w+)$")
    
    labels = {}
    for path in walk_script_files(game_path):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if label := label_re.search(line):
                labels[label.group(1)] = {
                    "path": str(path.relative_to(game_path)),
                    "lineno": i,
                }
                
    # now find all jumps and attribute their dest correctly
    for path in walk_script_files(game_path):
        current_label = None
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if match_label := label_re.search(line):
                current_label = match_label.group(1)
            if jump := jump_re.search(line):
                label = labels[jump.group(1)]
                yield {
                    "src_line": f"{path.relative_to(game_path)}:{i}",
                    "dst_line": f"{label['path']}:{label['lineno']}",
                    "src_label": current_label,
                    "dst_label": jump.group(1),
                }


def jumps_to_graph(jumps):
    """
    Convert jumps to a directed graph.
    
    Args:
        jumps: List of dictionaries containing jump information
        
    Returns:
        A NetworkX directed graph representing the jumps
    """
    g = nx.DiGraph()
    seen = defaultdict(int)
    
    for row in jumps:
        seen[row["src_label"]] += 1
        g.add_edge(
            row["src_label"],
            row["dst_label"],
        )

    return g