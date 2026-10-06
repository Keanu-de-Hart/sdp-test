"""Request models for the API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CloneRequest(BaseModel):
    url: str
    name: str | None = None


class MetricsFilters(BaseModel):
    start: int | None = None                  # inclusive UNIX timestamp (H_i,j / H_t)
    end: int | None = None                    # exclusive UNIX timestamp
    commits: list[str] = []                   # manually selected commit list
    authors: list[str] = []                   # author keys ('i:<email>' or 'm:<group id>')
    path: str | None = None
    object_type: Literal["file", "dir"] | None = None
    granularity: Literal["day", "week", "month"] = "month"
    limit: int = 500
    offset: int = 0
    only_changed: bool = False


class MergeRequest(BaseModel):
    identities: list[str]
    name: str = ""
