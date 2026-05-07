"""
Migration version management for the SWE Agent.

Handles migration versioning with simple incrementing numbers.
"""

import re
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MigrationVersion:
    """Represents a migration version with metadata."""
    
    number: int
    name: str
    filename: str
    description: Optional[str] = None
    
    @classmethod
    def from_filename(cls, filename: str) -> Optional['MigrationVersion']:
        """
        Parse a migration version from a filename.
        
        Expected format: 001_migration_name.py
        
        Args:
            filename: Migration filename
            
        Returns:
            MigrationVersion instance or None if invalid format
        """
        # Match pattern: 001_migration_name.py
        pattern = r'^(\d{3})_(.+)\.py$'
        match = re.match(pattern, filename)
        
        if not match:
            return None
        
        number = int(match.group(1))
        name = match.group(2)
        
        return cls(
            number=number,
            name=name,
            filename=filename
        )
    
    def __str__(self) -> str:
        return f"{self.number:03d}_{self.name}"
    
    def __lt__(self, other: 'MigrationVersion') -> bool:
        """Enable sorting by version number."""
        return self.number < other.number
    
    def __eq__(self, other: 'MigrationVersion') -> bool:
        """Enable equality comparison by version number."""
        return self.number == other.number


class MigrationVersionManager:
    """Manages migration versions and ordering."""
    
    def __init__(self, migrations_dir: Path):
        self.migrations_dir = migrations_dir
    
    def get_available_migrations(self) -> List[MigrationVersion]:
        """
        Get all available migration versions from the migrations directory.
        
        Returns:
            List of MigrationVersion instances sorted by version number
        """
        migrations = []
        
        if not self.migrations_dir.exists():
            return migrations
        
        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue
            
            version = MigrationVersion.from_filename(file_path.name)
            if version:
                migrations.append(version)
        
        # Sort by version number
        migrations.sort()
        return migrations
    
    def get_migration_by_number(self, number: int) -> Optional[MigrationVersion]:
        """
        Get a specific migration by its version number.
        
        Args:
            number: Migration version number
            
        Returns:
            MigrationVersion instance or None if not found
        """
        migrations = self.get_available_migrations()
        
        for migration in migrations:
            if migration.number == number:
                return migration
        
        return None
    
    def get_latest_migration(self) -> Optional[MigrationVersion]:
        """
        Get the latest migration version.
        
        Returns:
            Latest MigrationVersion instance or None if no migrations exist
        """
        migrations = self.get_available_migrations()
        
        if not migrations:
            return None
        
        return migrations[-1]  # Last item after sorting
    
    def get_next_version_number(self) -> int:
        """
        Get the next available version number for a new migration.
        
        Returns:
            Next version number (e.g., if latest is 003, returns 4)
        """
        latest = self.get_latest_migration()
        
        if latest is None:
            return 1
        
        return latest.number + 1
    
    def validate_migration_sequence(self) -> List[str]:
        """
        Validate that migration numbers form a continuous sequence.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        migrations = self.get_available_migrations()
        
        if not migrations:
            return errors
        
        # Check for gaps in sequence
        expected_number = 1
        for migration in migrations:
            if migration.number != expected_number:
                errors.append(f"Missing migration {expected_number:03d}, found {migration.number:03d}")
            expected_number = migration.number + 1
        
        # Check for duplicates
        numbers = [m.number for m in migrations]
        duplicates = set([n for n in numbers if numbers.count(n) > 1])
        
        for duplicate in duplicates:
            errors.append(f"Duplicate migration number: {duplicate:03d}")
        
        return errors 