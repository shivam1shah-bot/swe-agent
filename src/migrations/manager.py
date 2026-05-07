"""
Enhanced migration manager for the SWE Agent.

Provides migration execution with versioning, rollback, and dependency tracking.
"""

import logging
import importlib.util
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from .version import MigrationVersion, MigrationVersionManager

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Enhanced migration manager with versioning and rollback capabilities.
    """
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.migrations_dir = Path(__file__).parent / "scripts"
        self.version_manager = MigrationVersionManager(self.migrations_dir)
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Ensure the migration history table exists with correct schema."""
        with self.engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_name = 'migration_history'
            """))
            table_exists = result.fetchone()[0] > 0
            
            if table_exists:
                # Check if it has the new schema (version_number column)
                result = conn.execute(text("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.columns 
                    WHERE table_name = 'migration_history' AND column_name = 'version_number'
                """))
                has_version_column = result.fetchone()[0] > 0
                
                if not has_version_column:
                    logger.info("Upgrading migration_history table to new schema")
                    # Drop the old table and recreate with new schema
                    conn.execute(text("DROP TABLE migration_history"))
                    conn.execute(text("""
                        CREATE TABLE migration_history (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            version_number INT NOT NULL UNIQUE,
                            migration_name VARCHAR(255) NOT NULL,
                            filename VARCHAR(255) NOT NULL,
                            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            rollback_sql TEXT,
                            INDEX idx_version_number (version_number),
                            INDEX idx_applied_at (applied_at)
                        )
                    """))
                    logger.info("Migration history table upgraded to new schema")
            else:
                # Create new table with correct schema
                conn.execute(text("""
                    CREATE TABLE migration_history (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        version_number INT NOT NULL UNIQUE,
                        migration_name VARCHAR(255) NOT NULL,
                        filename VARCHAR(255) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rollback_sql TEXT,
                        INDEX idx_version_number (version_number),
                        INDEX idx_applied_at (applied_at)
                    )
                """))
                logger.info("Created new migration history table")
            
            conn.commit()
    
    def get_applied_migrations(self) -> List[int]:
        """
        Get list of applied migration version numbers.
        
        Returns:
            List of version numbers that have been applied
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT version_number FROM migration_history ORDER BY version_number"
            ))
            return [row[0] for row in result.fetchall()]
    
    def get_pending_migrations(self) -> List[MigrationVersion]:
        """
        Get list of pending migrations that need to be applied.
        
        Returns:
            List of MigrationVersion instances for pending migrations
        """
        applied = set(self.get_applied_migrations())
        available = self.version_manager.get_available_migrations()
        
        return [migration for migration in available if migration.number not in applied]
    
    def load_migration_module(self, migration: MigrationVersion):
        """
        Dynamically load a migration module.
        
        Args:
            migration: MigrationVersion instance
            
        Returns:
            Loaded migration module
        """
        migration_path = self.migrations_dir / migration.filename
        
        if not migration_path.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_path}")
        
        spec = importlib.util.spec_from_file_location(
            f"migration_{migration.number:03d}",
            migration_path
        )
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load migration: {migration_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    def apply_migration(self, migration: MigrationVersion) -> bool:
        """
        Apply a single migration.
        
        Args:
            migration: MigrationVersion instance
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Applying migration {migration}")
        
        try:
            # Load migration module
            module = self.load_migration_module(migration)
            
            if not hasattr(module, 'upgrade'):
                raise AttributeError(f"Migration {migration.filename} missing 'upgrade' function")
            
            # Apply the migration
            module.upgrade(self.engine)
            
            # Record in migration history
            rollback_sql = None
            if hasattr(module, 'downgrade'):
                # Store rollback information if available
                rollback_sql = getattr(module, '__rollback_sql__', None)
            
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO migration_history 
                    (version_number, migration_name, filename, rollback_sql)
                    VALUES (:version, :name, :filename, :rollback)
                """), {
                    "version": migration.number,
                    "name": migration.name,
                    "filename": migration.filename,
                    "rollback": rollback_sql
                })
                conn.commit()
            
            logger.info(f"Successfully applied migration {migration}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply migration {migration}: {e}")
            return False
    
    def rollback_migration(self, migration: MigrationVersion) -> bool:
        """
        Rollback a single migration.
        
        Args:
            migration: MigrationVersion instance
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Rolling back migration {migration}")
        
        try:
            # Load migration module
            module = self.load_migration_module(migration)
            
            if not hasattr(module, 'downgrade'):
                raise AttributeError(f"Migration {migration.filename} missing 'downgrade' function")
            
            # Rollback the migration
            module.downgrade(self.engine)
            
            # Remove from migration history
            with self.engine.connect() as conn:
                conn.execute(text(
                    "DELETE FROM migration_history WHERE version_number = :version"
                ), {"version": migration.number})
                conn.commit()
            
            logger.info(f"Successfully rolled back migration {migration}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback migration {migration}: {e}")
            return False
    
    def run_migrations(self) -> bool:
        """
        Run all pending migrations.
        
        Returns:
            True if all migrations successful, False otherwise
        """
        logger.info("Starting migration run")
        
        # Validate migration sequence
        errors = self.version_manager.validate_migration_sequence()
        if errors:
            logger.error("Migration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        # Get pending migrations
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return True
        
        logger.info(f"Found {len(pending)} pending migrations")
        
        # Apply each migration
        success_count = 0
        for migration in pending:
            if self.apply_migration(migration):
                success_count += 1
            else:
                logger.error(f"Migration run stopped at {migration}")
                break
        
        if success_count == len(pending):
            logger.info("All migrations applied successfully")
            return True
        else:
            logger.error(f"Applied {success_count}/{len(pending)} migrations")
            return False
    
    def rollback_to_version(self, target_version: int) -> bool:
        """
        Rollback migrations to a specific version.
        
        Args:
            target_version: Version number to rollback to
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Rolling back to version {target_version}")
        
        applied = self.get_applied_migrations()
        available = self.version_manager.get_available_migrations()
        
        # Find migrations to rollback (in reverse order)
        to_rollback = []
        for version_num in reversed(applied):
            if version_num <= target_version:
                break
            
            # Find the migration version object
            migration = self.version_manager.get_migration_by_number(version_num)
            if migration:
                to_rollback.append(migration)
        
        if not to_rollback:
            logger.info(f"Already at or below version {target_version}")
            return True
        
        logger.info(f"Rolling back {len(to_rollback)} migrations")
        
        # Rollback each migration
        success_count = 0
        for migration in to_rollback:
            if self.rollback_migration(migration):
                success_count += 1
            else:
                logger.error(f"Rollback stopped at {migration}")
                break
        
        if success_count == len(to_rollback):
            logger.info(f"Successfully rolled back to version {target_version}")
            return True
        else:
            logger.error(f"Rolled back {success_count}/{len(to_rollback)} migrations")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """
        Get current migration status.
        
        Returns:
            Dictionary containing migration status information
        """
        applied = self.get_applied_migrations()
        available = self.version_manager.get_available_migrations()
        pending = self.get_pending_migrations()
        
        current_version = max(applied) if applied else 0
        latest_version = available[-1].number if available else 0
        
        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "applied_count": len(applied),
            "available_count": len(available),
            "pending_count": len(pending),
            "up_to_date": len(pending) == 0,
            "applied_migrations": applied,
            "pending_migrations": [m.number for m in pending]
        } 