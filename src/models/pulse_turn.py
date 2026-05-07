"""
Pulse Turn model — one row per AI assistant turn (conversation response).
Source of truth for token usage and cost.
"""

import time

from sqlalchemy import Column, Float, Index, Integer, JSON, String, Text

from .base import Base
from src.utils.connector import generate_id


class PulseTurn(Base):
    __tablename__ = "pulse_turns"

    id = Column(String(14), primary_key=True, default=generate_id)
    prompt_id = Column(String(255), unique=True, index=True)
    session_id = Column(String(255))
    repo = Column(String(255), nullable=False, index=True)
    branch = Column(String(255))
    author_email = Column(String(255), index=True)
    user_prompt = Column(Text)
    user_prompt_ts = Column(String(50))
    assistant_turn_ts = Column(String(50))
    timestamp = Column(String(50))
    unix_ts = Column(Float, index=True)
    model = Column(String(100))
    turn_type = Column(String(50))
    tools_used = Column(JSON)
    skill_invoked = Column(String(255))
    cost_usd = Column(Float)
    assistant_preview = Column(Text)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))
