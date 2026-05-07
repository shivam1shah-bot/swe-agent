"""
Pulse CommitPrompt model — junction between commits and the prompts used in them.
"""

import time

from sqlalchemy import Column, Float, Index, Integer, JSON, String, Text

from .base import Base
from src.utils.connector import generate_id


class PulseCommitPrompt(Base):
    __tablename__ = "pulse_commit_prompts"

    id = Column(String(14), primary_key=True, default=generate_id)
    commit_id = Column(String(14), nullable=False, index=True)
    prompt = Column(Text)
    timestamp = Column(String(50))
    model = Column(String(100))
    turn_type = Column(String(50))
    cost_usd = Column(Float, nullable=False, default=0.0)
    tools_used = Column(JSON)
    skill_invoked = Column(String(255))
    assistant_preview = Column(Text)
    turn_id = Column(String(14), nullable=True, index=True)
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))
