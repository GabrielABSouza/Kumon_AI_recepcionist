# app/core/database/__init__.py
"""Database module init"""

from .connection import get_database_connection

__all__ = ["get_database_connection"]