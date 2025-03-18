"""Extract and prepare choices for TTS generation."""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from princess.choices import extract_script_structure
from princess.constants import CHARACTERS
from princess.utils.text import clean_text_for_voice
from princess.utils.file import walk_script_files


def clean_choice_for_tts(choice_text: str) -> str:
    """Clean a choice text for TTS processing.
    
    Args:
        choice_text: The raw choice text from the game
        
    Returns:
        Cleaned text suitable for TTS
    """
    return clean_text_for_voice(choice_text)


def get_choice_hash(choice_text: str) -> str:
    """Generate a SHA-256 hash of the choice text.
    
    Args:
        choice_text: The choice text
        
    Returns:
        SHA-256 hex digest of the choice text
    """
    return hashlib.sha256(choice_text.encode('utf-8')).hexdigest()


def extract_choices_from_file(script_path: str) -> List[Dict[str, Any]]:
    """Extract choices from a Ren'Py script file.
    
    Args:
        script_path: Path to the script file
        
    Returns:
        List of enriched choice data
    """
    # Extract choices using the existing functionality
    choices, _ = extract_script_structure(
        script_path,
        CHARACTERS,
        export_specific_json=None  # Don't export, just return the data
    )
    
    # Enrich with TTS-specific data
    enriched_choices = []
    for item in choices:
        choice = item["choice"]
        choice_text = choice.text
        
        # Skip empty choices or system choices
        if not choice_text or choice_text == "Say nothing.":
            continue
            
        # Get context before and after
        context_before = sorted(item["context_before"], key=lambda d: d.node_id)
        context_after = sorted(item["context_after"], key=lambda d: d.node_id)
        
        # Filter out lines starting with "Note: You can skip" or containing "{fast}"
        context_before = [
            d for d in context_before 
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        context_after = [
            d for d in context_after 
            if not (d.text and (d.text.startswith("Note: You can skip") or "{fast}" in d.text))
        ]
        
        # Get the last 3 items of context before and first 3 items of context after
        context_before = context_before[-3:] if len(context_before) > 3 else context_before
        context_after = context_after[:3] if len(context_after) > 3 else context_after
        
        # Format contexts
        formatted_context_before = []
        for dialogue in context_before:
            formatted_context_before.append({
                "character": dialogue.character,
                "text": dialogue.text,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            })
            
        formatted_context_after = []
        for dialogue in context_after:
            formatted_context_after.append({
                "character": dialogue.character,
                "text": dialogue.text,
                "voice": dialogue.voice,
                "label": dialogue.label,
                "node_id": dialogue.node_id,
            })
            
        # Get the current label from the choice
        current_label = choice.label_path[-1] if choice.label_path else None
        
        # Generate the clean TTS text and hash
        clean_tts_text = clean_choice_for_tts(choice_text)
        choice_hash = get_choice_hash(choice_text)
        
        # Add to the enriched choices
        enriched_choices.append({
            "filename": os.path.basename(script_path),
            "lineno": -1,  # Placeholder
            "current_label": current_label,
            "choice_text": choice_text,
            "clean_tts_text": clean_tts_text,
            "choice_hash": choice_hash,
            "context_before": formatted_context_before,
            "context_after": formatted_context_after,
        })
    
    return enriched_choices


def extract_all_choices(game_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Extract choices from all script files in the game.
    
    Args:
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
        
    Returns:
        List of all enriched choice data
    """
    # Get all script files using the utility function
    script_files = list(walk_script_files(game_path))
    
    all_choices = []
    for script_file in script_files:
        try:
            choices = extract_choices_from_file(str(script_file))
            all_choices.extend(choices)
        except Exception as e:
            print(f"Error processing {script_file}: {e}")
    
    return all_choices


def export_choices_for_tts(output_file: str, game_path: Optional[Union[str, Path]] = None) -> None:
    """Extract choices and export them to a JSON file for TTS processing.
    
    Args:
        output_file: Path to the output JSON file
        game_path: Optional path to game directory. If None, uses GAME_PATH env variable.
    """
    all_choices = extract_all_choices(game_path)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_choices, f, indent=2)
    
    print(f"Exported {len(all_choices)} choices to {output_file}")
