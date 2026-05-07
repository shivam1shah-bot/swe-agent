"""
Pulse Edit model — one row per file edit made by AI.
"""

import time

from sqlalchemy import Column, Float, Index, Integer, JSON, String, Text
from .base import Base
from src.utils.connector import generate_id


class PulseEdit(Base):
    __tablename__ = "pulse_edits"

    id = Column(String(14), primary_key=True, default=generate_id)
    prompt_id = Column(String(255), index=True)
    session_id = Column(String(255))
    repo = Column(String(255), nullable=False, index=True)
    branch = Column(String(255))
    author_email = Column(String(255), index=True)
    timestamp = Column(String(50))
    unix_ts = Column(Float, index=True)
    tool_category = Column(String(50))
    tool_name = Column(String(100))
    file_edited = Column(Text)
    files_changed = Column(JSON)
    files_new = Column(JSON)
    lines_added_by_ai = Column(Integer, nullable=False, default=0)
    lines_removed_by_ai = Column(Integer, nullable=False, default=0)
    diff_stats = Column(JSON)
    model = Column(String(100))
    prompt = Column(Text)
    skill_invoked = Column(String(255))
    assistant_preview = Column(Text)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    session_cost_usd = Column(Float)
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))
