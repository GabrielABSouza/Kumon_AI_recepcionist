"""
Database Connection Manager - PostgreSQL connection with robust fallback
Provides reliable database access with graceful degradation
"""

import os
import logging
import psycopg2
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager with automatic pooling and fallback"""
    
    def __init__(self):
        self._connection = None
        self._connection_params = None
        self._connected = False
    
    def _parse_database_url(self) -> Optional[Dict[str, Any]]:
        """Parse DATABASE_URL environment variable"""
        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not found in environment")
                return None
                
            result = urlparse(database_url)
            
            return {
                'host': result.hostname,
                'port': result.port,
                'database': result.path[1:],  # Remove leading '/'
                'user': result.username,
                'password': result.password,
                'sslmode': 'require'  # Railway requires SSL
            }
        except Exception as e:
            logger.error(f"Error parsing DATABASE_URL: {e}")
            return None
    
    def get_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        Get database connection with automatic retry and fallback
        
        Returns:
            Optional[connection]: Database connection or None if unavailable
        """
        # Try to reuse existing connection
        if self._connection and not self._connection.closed:
            try:
                # Test connection
                with self._connection.cursor() as cur:
                    cur.execute("SELECT 1")
                return self._connection
            except:
                self._connection = None
        
        # Create new connection
        return self._create_connection()
    
    def _create_connection(self) -> Optional[psycopg2.extensions.connection]:
        """Create new database connection"""
        try:
            if not self._connection_params:
                self._connection_params = self._parse_database_url()
                
            if not self._connection_params:
                logger.warning("No database configuration available")
                return None
            
            logger.info("Connecting to PostgreSQL database...")
            
            self._connection = psycopg2.connect(**self._connection_params)
            self._connection.autocommit = True  # Auto-commit for simplicity
            self._connected = True
            
            logger.info("✅ Database connection established")
            return self._connection
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self._connection = None
            self._connected = False
            return None
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        if not self._connection or self._connection.closed:
            return False
        try:
            with self._connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except:
            self._connected = False
            return False
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            try:
                self._connection.close()
            except:
                pass
        self._connection = None
        self._connected = False


# Global database manager
_db_manager = DatabaseManager()


def get_database_connection():
    """
    Get database connection with robust fallback
    
    Returns:
        Connection object or None if database unavailable
        Falls back gracefully to prevent application crashes
    """
    try:
        return _db_manager.get_connection()
    except Exception as e:
        logger.warning(f"Database connection unavailable, degrading gracefully: {e}")
        return None


# Legacy compatibility
def get_db_connection():
    """Legacy function name compatibility"""
    return get_database_connection()