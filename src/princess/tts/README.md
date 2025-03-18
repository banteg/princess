# TTS Module for Slay the Princess

This module helps with generating and managing Text-to-Speech (TTS) audio for player choice options in Slay the Princess.

## Features

1. **Extract Choices**: Extract all player choices from game scripts with context
2. **Clean Text**: Process choice text for TTS generation
3. **Track TTS Files**: Manage TTS files in a SQLite database
4. **Label Interface**: TUI interface for labeling/approving TTS files
5. **Context Playback**: Play choices with surrounding dialogue context

## Usage

### Exporting Choices for TTS

```bash
princess-tts export --output choices_for_tts.json --dir /path/to/scripts
```

This exports all player choices from the game scripts to a JSON file, which you can then use with your TTS generation system.

### Setting Up the Database

```bash
princess-tts setup --db tts_choices.db --tts-dir /path/to/tts/files --script-dir /path/to/scripts
```

This creates a SQLite database to track TTS files and their approval status.

### Labeling TTS Files

```bash
princess-tts label --db tts_choices.db --tts-dir /path/to/tts/files
```

This launches the TUI interface for labeling/approving TTS files. Use the following keyboard shortcuts:

- `p`: Play the current TTS file
- `s`: Stop playback
- `1`, `2`, `3`: Play with 1, 2, or 3 lines of context (experimental)
- `a`: Approve the current TTS file
- `r`: Reject the current TTS file
- `n`: Skip to the next file
- `q`: Quit

## File Naming Convention

TTS files should be placed in the TTS directory with filenames matching the SHA-256 hash of the choice text, with a .flac extension.

For example, if the choice text is "I'll help you escape", the filename would be:
```
c9f25d5bbee2cdf9252d9696ee5200f9fb7d9c1c2dd1eef583be205065f355e5.flac
```

## Database Schema

The module uses a SQLite database with two main tables:

1. **choices**: Stores choice text and context
2. **tts_files**: Tracks TTS files and their approval status

When TTS files are replaced or modified, the system automatically detects this by comparing file hashes and resets the approval status.