"""
Base models and shared components for the SWE Agent.
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum

# Create base class for models
Base = declarative_base()

# Task status enum
class TaskStatus(enum.Enum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled" 