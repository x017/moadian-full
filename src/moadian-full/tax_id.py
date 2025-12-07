"""
Tax ID Generator for Iranian Moadian System
"""

import time
from datetime import datetime
from typing import Optional
from .verhoeff import Verhoeff


class TaxIdGenerator:
    """
    Generates valid Tax IDs for Moadian invoices
    
    Tax ID Format (22 characters):
    - Memory ID: 6 chars (fiscal_id)
    - Days: 5 chars (hex of days since epoch)
    - Serial: 10 chars (hex of serial number)
    - Check: 1 char (Verhoeff check digit)
    """
    
    def __init__(self, fiscal_id: str):
        """
        Initialize Tax ID Generator
        
        Args:
            fiscal_id: 6-character fiscal memory ID (e.g., "A3NFZT")
        """
        if len(fiscal_id) != 6:
            raise ValueError(f"fiscal_id must be 6 characters, got {len(fiscal_id)}")
        
        self.fiscal_id = fiscal_id.upper()
    
    @staticmethod
    def char_to_value(c: str) -> str:
        """
        Convert character to numeric value for Verhoeff calculation
        
        Important: This uses Base36 mapping, NOT ASCII!
        - 0-9 → '0'-'9'
        - A-Z → '10'-'35'
        
        Args:
            c: Single character
            
        Returns:
            String representation of numeric value
        """
        if c.isdigit():
            return c
        else:
            # A=10, B=11, ..., Z=35
            return str(ord(c.upper()) - 55)
    
    def generate(self, timestamp_ms: Optional[int] = None, serial: Optional[int] = None) -> str:
        """
        Generate a valid Tax ID
        
        Args:
            timestamp_ms: Timestamp in milliseconds (default: current time)
            serial: Serial number (default: auto-generated)
            
        Returns:
            22-character Tax ID string
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        if serial is None:
            # Generate unique serial from timestamp
            import random
            ts = int(time.time())
            rand = random.randint(10, 99)
            serial = (ts % 10000000000) * 100 + rand
        
        # Part 1: Memory ID (6 chars)
        part1 = self.fiscal_id
        
        # Part 2: Days since epoch (5 hex chars)
        days = int(timestamp_ms / 86400000)
        part2 = format(days, 'X').upper().zfill(5)
        
        # Part 3: Serial (10 hex chars)
        part3 = format(serial, 'X').upper().zfill(10)
        
        # Base (21 chars)
        base = part1 + part2 + part3
        
        # Convert to numeric for Verhoeff
        numeric = ''.join(self.char_to_value(c) for c in base)
        
        # Calculate check digit
        check = Verhoeff.calculate(numeric)
        
        # Final Tax ID (22 chars)
        return base + str(check)
    
    def get_invoice_number(self, serial: int) -> str:
        """
        Generate invoice number from serial
        Must match the serial portion of Tax ID
        
        Args:
            serial: Serial number
            
        Returns:
            10-character hex string
        """
        return format(serial, 'X').upper().zfill(10)
    
    def validate(self, tax_id: str) -> bool:
        """
        Validate a Tax ID
        
        Args:
            tax_id: 22-character Tax ID
            
        Returns:
            True if valid, False otherwise
        """
        if len(tax_id) != 22:
            return False
        
        base = tax_id[:21]
        check = tax_id[21]
        
        numeric = ''.join(self.char_to_value(c) for c in base)
        calculated_check = Verhoeff.calculate(numeric)
        
        return str(calculated_check) == check
