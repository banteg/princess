import re
import json
from pathlib import Path

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


# Direct approach to parsing Ren'Py script, focusing on extracting choices and their context
def parse_script(path):
    # Regex patterns for different script elements
    character_re = re.compile(r"^\s*(" + "|".join(characters) + r")\s+\"(.+)\"")
    label_re = re.compile(r"^\s*label\s+(\w+):")
    menu_re = re.compile(r"^\s*menu:")
    choice_re = re.compile(r'^\s+\"(.+?)\"')  # Matches indented choices
    voice_re = re.compile(r'^\s*voice\s+"([^"]+)"')

    # Data structures
    dialogues = []        # All dialogue lines
    menus = []            # Menus with context
    label_dialogues = {}  # Dialogues organized by label
    
    # State tracking
    current_label = None
    current_menu = None
    in_menu = False
    
    # First pass: gather all dialogues and organize by label
    for line_num, line in enumerate(Path(path).read_text().splitlines(), 1):
        # Track labels
        if label_match := label_re.search(line):
            current_label = label_match.group(1)
            # Initialize dialogues array for this label if needed
            if current_label not in label_dialogues:
                label_dialogues[current_label] = []
            in_menu = False
            continue
        
        # Track menu sections
        if menu_re.search(line):
            in_menu = True
            current_menu = {
                "label": current_label,
                "context": [],  # Will be filled later
                "choices": []
            }
            menus.append(current_menu)
            continue
        
        # Process choices
        if in_menu and (choice_match := choice_re.search(line)):
            choice_text = choice_match.group(1)
            # Clean up Ren'Py formatting tags
            choice_text = re.sub(r'\{[^}]+\}', '', choice_text)
            if "•" in choice_text:
                choice_text = choice_text.replace("• ", "")
            
            current_menu["choices"].append({
                "choice": choice_text,
                "line": line_num
            })
            continue
        
        # Voice lines belong to the previous dialogue
        if voice_match := voice_re.search(line):
            voice_path = voice_match.group(1)
            # Find the most recent dialogue without a voice
            if dialogues and dialogues[-1]["voice"] is None:
                dialogues[-1]["voice"] = voice_path
                
                # Also update in label_dialogues
                if current_label in label_dialogues and label_dialogues[current_label]:
                    for d in reversed(label_dialogues[current_label]):
                        if d["voice"] is None:
                            d["voice"] = voice_path
                            break
            continue
        
        # Process dialogue lines
        if dialogue_match := character_re.search(line):
            char = dialogue_match.group(1)
            dialogue_text = dialogue_match.group(2).strip()
            
            # Clean up the text
            dialogue_text = dialogue_text.replace(r'\n', '')  # Remove newline escapes
            dialogue_text = re.sub(r'\{[^}]+\}', '', dialogue_text)  # Remove formatting tags
            
            # Create the dialogue entry
            entry = {
                "character": char,
                "text": dialogue_text,
                "voice": None,
                "label": current_label,
                "line": line_num
            }
            
            # Add to both overall dialogues and label-specific dialogues
            dialogues.append(entry)
            if current_label in label_dialogues:
                label_dialogues[current_label].append(entry)
    
    # Second pass: Populate context for each menu by traversing label dependencies
    for menu in menus:
        if menu["label"] in label_dialogues:
            # Add all dialogues from the current label
            menu["context"] = label_dialogues[menu["label"]].copy()
            
            # Merge voice and text in context dialogues for user convenience 
            merged_context = []
            for entry in menu["context"]:
                merged_entry = {
                    "character": entry["character"],
                    "text": entry["text"],
                    "voice": entry["voice"],
                    "line": entry["line"]
                }
                merged_context.append(merged_entry)
            
            menu["merged_context"] = merged_context
    
    # Create a final output structure with all extracted information
    return {
        "dialogues": dialogues,
        "menus": menus,
        "label_dialogues": label_dialogues  # Include for debugging
    }


# Example usage:
if __name__ == "__main__":
    import pprint

    print("Parsing Ren'Py script file...")
    result = parse_script("script.rpy")
    
    # Print results summary
    print(f"\nExtracted {len(result['dialogues'])} dialogue lines")
    print(f"Extracted {len(result['menus'])} menu choices with context")
    
    # Print sample of the first menu with context
    if result['menus']:
        print("\nSample menu with context:")
        menu = result['menus'][0]
        print(f"Label: {menu.get('label', 'Unknown')}")
        print(f"Context length: {len(menu['context'])} dialogue entries")
        print(f"Choices: {len(menu.get('choices', []))} options")
        
        # Show first few dialogue entries from context
        if menu['context']:
            print("\nContext sample (up to 3 entries):")
            for i, entry in enumerate(menu['context'][:3]):
                print(f"  {i+1}. {entry['character']}: {entry['text'][:50]}...")
                if entry['voice']:
                    print(f"     Voice: {entry['voice']}")
        
        # Show first few choices
        if menu.get('choices', []):
            print("\nChoices sample (up to 3):")
            for i, choice in enumerate(menu.get('choices', [])[:3]):
                print(f"  {i+1}. {choice.get('choice', '')[:50]}...")
                
        # Show merged context and choices for the menu
        if 'merged_context' in menu:
            print("\nMerged context and choices example:")
            merged_data = {
                "label": menu["label"],
                "context": [f"{e['character']}: {e['text'][:30]}..." for e in menu["merged_context"][:2]],
                "choices": [c["choice"][:30] + "..." for c in menu["choices"][:2]]
            }
            pprint.pprint(merged_data, width=100)
    
    # Write full results to files for inspection
    with open('parser_output.txt', 'w') as f:
        pprint.pprint(result, f, width=120)
    
    # Also save as JSON for easier programmatic access
    with open('parser_output.json', 'w') as f:
        json.dump(result, f, indent=2)
        
    print("\nFull output written to parser_output.txt and parser_output.json")