"""Database management for TTS files."""

import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

import sqlite_utils


class TTSDatabase:
    """Manage TTS files and their metadata in a SQLite database."""
    
    def __init__(self, db_path: str = "tts_choices.db"):
        """Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db = sqlite_utils.Database(db_path)
        self._init_schema()
        
    def _init_schema(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        # Choices table
        if "choices" not in self.db.table_names():
            self.db["choices"].create({
                "choice_hash": str,           # SHA-256 hash of the original choice text
                "choice_text": str,           # Original choice text
                "clean_tts_text": str,        # Cleaned text for TTS
                "filename": str,              # Source filename
                "current_label": str,         # Label in the game script
                "context_before": str,        # JSON string of context before
                "context_after": str,         # JSON string of context after
                "created_at": str,           # Creation timestamp
                "updated_at": str            # Last update timestamp
            }, pk="choice_hash")
            
            # Add index on filename
            self.db["choices"].create_index(["filename"])
        
        # TTS Files table
        if "tts_files" not in self.db.table_names():
            self.db["tts_files"].create({
                "id": int,                   # Auto-incremented ID
                "choice_hash": str,          # References choices.choice_hash
                "file_path": str,            # Path to the TTS file
                "file_hash": str,            # SHA-256 hash of the file contents
                "status": str,               # Status: 'pending', 'approved', 'rejected'
                "created_at": str,          # Creation timestamp
                "updated_at": str           # Last update timestamp
            }, pk="id")
            
            # Add indexes
            self.db["tts_files"].create_index(["choice_hash"])
            self.db["tts_files"].create_index(["status"])
            
    def import_choices(self, choices: List[Dict[str, Any]]) -> None:
        """Import choices into the database.
        
        Args:
            choices: List of choice data to import
        """
        import json
        from datetime import datetime
        
        now = datetime.now().isoformat()
        
        # Prepare data for bulk insert
        choice_rows = []
        for choice in choices:
            choice_row = {
                "choice_hash": choice["choice_hash"],
                "choice_text": choice["choice_text"],
                "clean_tts_text": choice["clean_tts_text"],
                "filename": choice["filename"],
                "current_label": choice["current_label"] or "",
                "context_before": json.dumps(choice["context_before"]),
                "context_after": json.dumps(choice["context_after"]),
                "created_at": now,
                "updated_at": now
            }
            choice_rows.append(choice_row)
        
        # Insert choices, ignoring duplicates
        self.db["choices"].upsert_all(choice_rows, pk="choice_hash", alter=True)
    
    def scan_tts_directory(self, tts_dir: str) -> None:
        """Scan a directory for TTS files and update the database.
        
        Args:
            tts_dir: Directory containing TTS files
        """
        from datetime import datetime
        
        now = datetime.now().isoformat()
        tts_path = Path(tts_dir)
        
        # Get all FLAC files in the directory
        flac_files = list(tts_path.glob("*.flac"))
        
        for flac_file in flac_files:
            # Extract choice hash from filename
            choice_hash = flac_file.stem
            
            # Check if the choice exists
            choice = self.db["choices"].get(choice_hash)
            if not choice:
                print(f"Warning: Found TTS file {flac_file} with no matching choice")
                continue
                
            # Calculate file hash
            with open(flac_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Check if we already have this file
            existing_files = list(self.db["tts_files"].rows_where(
                "choice_hash = ? AND file_path = ?",
                [choice_hash, str(flac_file)]
            ))
            
            if existing_files:
                existing_file = existing_files[0]
                # If the file has changed, update the hash and status
                if existing_file["file_hash"] != file_hash:
                    self.db["tts_files"].update(
                        existing_file["id"],
                        {
                            "file_hash": file_hash,
                            "status": "pending",  # Reset to pending if file has changed
                            "updated_at": now
                        }
                    )
            else:
                # Add new file
                self.db["tts_files"].insert({
                    "choice_hash": choice_hash,
                    "file_path": str(flac_file),
                    "file_hash": file_hash,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now
                })
    
    def update_file_status(self, file_id: int, status: str) -> None:
        """Update the status of a TTS file.
        
        Args:
            file_id: ID of the file to update
            status: New status ('pending', 'approved', 'rejected')
        """
        from datetime import datetime
        
        valid_statuses = ['pending', 'approved', 'rejected']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        
        self.db["tts_files"].update(
            file_id,
            {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
        )
    
    def get_next_pending_file(self) -> Optional[Dict[str, Any]]:
        """Get the next pending TTS file for review.
        
        Returns:
            File data including associated choice, or None if no pending files
        """
        # Get the next pending file
        pending_files = list(self.db["tts_files"].rows_where(
            "status = 'pending'",
            order_by="updated_at"
        ))
        
        if not pending_files:
            return None
            
        file_data = pending_files[0]
        choice_hash = file_data["choice_hash"]
        
        # Get the associated choice
        choice = self.db["choices"].get(choice_hash)
        if not choice:
            return None
            
        import json
        # Combine file and choice data
        result = {
            **file_data,
            "choice_text": choice["choice_text"],
            "clean_tts_text": choice["clean_tts_text"],
            "filename": choice["filename"],
            "current_label": choice["current_label"],
            "context_before": json.loads(choice["context_before"]),
            "context_after": json.loads(choice["context_after"]),
        }
        
        return result
        
    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Get a TTS file by ID with associated choice data.
        
        Args:
            file_id: ID of the file to retrieve
            
        Returns:
            File data including associated choice, or None if not found
        """
        file_data = self.db["tts_files"].get(file_id)
        if not file_data:
            return None
            
        choice_hash = file_data["choice_hash"]
        choice = self.db["choices"].get(choice_hash)
        if not choice:
            return None
            
        import json
        # Combine file and choice data
        result = {
            **file_data,
            "choice_text": choice["choice_text"],
            "clean_tts_text": choice["clean_tts_text"],
            "filename": choice["filename"],
            "current_label": choice["current_label"],
            "context_before": json.loads(choice["context_before"]),
            "context_after": json.loads(choice["context_after"]),
        }
        
        return result
        
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the TTS files.
        
        Returns:
            Dictionary with statistics
        """
        total_choices = self.db["choices"].count
        total_files = self.db["tts_files"].count
        
        pending_count = self.db["tts_files"].count_where("status = 'pending'")
        approved_count = self.db["tts_files"].count_where("status = 'approved'")
        rejected_count = self.db["tts_files"].count_where("status = 'rejected'")
        
        return {
            "total_choices": total_choices,
            "total_files": total_files,
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count
        }
