"""
Shared types used across all four tracks.

Dev 3 (retrieval) implements the search endpoint using these models.
Dev 4 (bot) calls that endpoint and consumes the same models.

If this file needs to change, flag it to the whole team the same day —
both tracks build directly against these shapes.
"""

from pydantic import BaseModel


class Citation(BaseModel):
    thread_id: str
    permalink: str
    snippet: str


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    answer: str
    citations: list[Citation]
