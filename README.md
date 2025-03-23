# Slay the Princess - Game Tools

A Python toolkit for working with the game files of "Slay the Princess," a narrative horror game with branching storylines.

## Overview

This project provides utilities for parsing, analyzing, and working with the game files of "Slay the Princess." It includes tools for extracting dialogue, choices, characters, and generating voice lines using text-to-speech technology.

## Features

- **Script Parsing**: Parse the game's `.rpy` script files into structured data
- **Choice Extraction**: Identify and extract player choices from the game scripts
- **Character Tracking**: Extract and work with character information
- **Voice Generation**: Generate voice lines for player choices using ML-based text-to-speech
- **Command-line Interface**: Easy-to-use CLI for all functionality
- **Marimo Notebook**: Interactive Python notebook for exploring and visualizing game data

## Installation

Requires Python 3.12+

```bash
# Clone the repository
git clone https://github.com/banteg/slay-the-princess.git
cd slay-the-princess

# Install using UV (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

## Usage

### Command Line Interface

The project provides a command-line interface with several subcommands:

```bash
# List available commands
princess --help

# Parse game scripts
princess parser <command>

# Work with player choices
princess choices <command>

# Extract character information
princess characters <command>

# Generate voice lines
princess sesame <command>
```

### Voice Generation Example

Generate speech for a specific line:

```bash
princess sesame generate "What do you want me to do?" --output output/line.flac --play
```

Process choices from a script file:

```bash
princess sesame process path/to/script.rpy
```

### Marimo Notebook

The project includes an interactive Marimo notebook for exploring game data:

```bash
# Run the Marimo notebook
marimo edit princess_marimo.py
```

## Project Structure

- `src/princess/`: Core library modules
  - `parser.py`: Script parsing functionality
  - `choices.py`: Choice extraction
  - `characters.py`: Character extraction and management
  - `voice.py`: Voice generation with ML-based TTS
  - `game.py`: Game-related utilities
  - `cli.py`: Command-line interface
- `tests/`: Unit tests
- `output/`: Generated output files

## Dependencies

- Text parsing: `lark`
- Data processing: `polars`
- TTS model: `csm-mlx`
- Audio handling: `audiofile`, `audresample`, `mutagen`
- CLI: `typer`, `rich`
- Interactive notebook: `marimo`

## License

MIT