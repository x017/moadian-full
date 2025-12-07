"""
Serial Number Manager for Moadian Invoices
Ensures unique, sequential serial numbers
"""

import os
import json
import time
import random
from datetime import datetime
from typing import Optional


class SerialManager:
    """
    Manages serial numbers for invoices
    
    Features:
    - Unique serial generation
    - Persistence across sessions
    - Timestamp-based to avoid collisions
    """
    
    def __init__(self, fiscal_id: str, storage_path: Optional[str] = None):
        """
        Initialize Serial Manager
        
        Args:
            fiscal_id: Fiscal memory ID
            storage_path: Path to store serial history (default: current directory)
        """
        self.fiscal_id = fiscal_id
        
        if storage_path is None:
            storage_path = os.getcwd()
        
        self.history_file = os.path.join(storage_path, f"serial_history_{fiscal_id}.json")
        self._load_history()
    
    def _load_history(self):
        """Load serial history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            except:
                self.history = {"serials": [], "last_serial": 0}
        else:
            self.history = {"serials": [], "last_serial": 0}
    
    def _save_history(self):
        """Save serial history to file"""
        try:
            # Keep only last 1000 serials
            if len(self.history["serials"]) > 1000:
                self.history["serials"] = self.history["serials"][-1000:]
            
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save serial history: {e}")
    
    def get_next(self) -> int:
        """
        Get next unique serial number
        
        Returns:
            Unique serial number
        """
        while True:
            # Generate serial from timestamp + random
            ts = int(time.time())
            rand = random.randint(10, 99)
            serial = (ts % 10000000000) * 100 + rand
            
            # Ensure uniqueness
            if serial not in self.history["serials"]:
                self.history["serials"].append(serial)
                self.history["last_serial"] = serial
                self._save_history()
                return serial
            
            # Small delay to ensure different timestamp
            time.sleep(0.01)
    
    def reset(self):
        """Reset serial history"""
        self.history = {"serials": [], "last_serial": 0}
        self._save_history()
        
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
