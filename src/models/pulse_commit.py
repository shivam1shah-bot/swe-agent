"""
Pulse Commit model — one row per git commit with AI attribution.
"""

import time

from sqlalchemy import Column, Float, Index, Integer, JSON, String, Text

from .base import Base
from src.utils.connector import generate_id


class PulseCommit(Base):
    __tablename__ = "pulse_commits"

    id = Column(String(14), primary_key=True, default=generate_id)
    commit_hash = Column(String(64), nullable=False, unique=True, index=True)
    repo = Column(String(255), nullable=False, index=True)
    branch = Column(String(255))
    author_email = Column(String(255), index=True)
    commit_author = Column(String(255))
    commit_message = Column(Text)
    commit_timestamp = Column(String(50))
    timestamp = Column(String(50))
    unix_ts = Column(Float, index=True)
    files_changed = Column(Integer, nullable=False, default=0)
    diff_summary = Column(Text)
    prompt_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=False, default=0.0)
    total_lines_added = Column(Integer, nullable=False, default=0)
    ai_lines = Column(Integer, nullable=False, default=0)
    human_lines = Column(Integer, nullable=False, default=0)
    ai_percentage = Column(Float, nullable=False, default=0.0)
    file_attribution = Column(JSON)
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))
