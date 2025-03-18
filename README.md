# Slay the Princess

Utilities for working with Slay the Princess game files.

## Features

- Extract character definitions
- Extract voice lines with associated metadata
- Extract menu choices
- Find labels and jumps between scenes
- Generate a graph representation of script flow
- Clean text for TTS processing

## Installation

```bash
uv add git+https://github.com/banteg/slay-the-princess.git
```

## Usage

Set the game path environment variable:

```bash
export GAME_PATH=/path/to/slay_the_princess
```

Then use the utilities:

```python
from princess.utils import extract_voice_lines, extract_choices

# Get all voice lines
voice_lines = list(extract_voice_lines())

# Get all menu choices
choices = list(extract_choices())

# Find all jumps between labels in the script
from princess.utils import find_labels_and_jumps, jumps_to_graph
import networkx as nx

jumps = list(find_labels_and_jumps())
graph = jumps_to_graph(jumps)
nx.write_graphml(graph, "output/jumps.graphml")
```

## Development

Clone the repository:

```bash
git clone https://github.com/banteg/slay-the-princess.git
cd slay-the-princess
```

Install development dependencies:

```bash
uv add -e dev .
```

Run linting:

```bash
ruff check src tests --fix --unsafe-fixes
```
