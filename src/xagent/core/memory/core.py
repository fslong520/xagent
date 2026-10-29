from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


class MemoryNote(BaseModel):
    content: Union[str, bytes]
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str = "general"
    timestamp: datetime = Field(default_factory=datetime.now)
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Shared-layer provenance (design §A2): which shared space the note lives in, so every
    # consumer (search results, injection) can label a team-visible quote as such.
    space_kind: Optional[str] = None
    space_id: Optional[int] = None


class MemoryResponse(BaseModel):
    success: bool
    memory_id: Optional[str] = None
    content: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = Field(default_factory=lambda: {})
    search_results: Optional[list[Any]] = None


def _normalized_body_text(value: Any) -> str:
    """Lower-case body text with every whitespace run collapsed (X-06).

    A rewritten note may differ only in line breaks, so a tag check has to
    compare bodies the way a reader would, not byte for byte.
    """
    return " ".join(str(value or "").split()).lower()


def drop_replaced_tags(note: "MemoryNote", previous_content: Any) -> list[str]:
    """Remove tags and keywords that only the old text supported.

    Rewriting a note's body used to leave the old values in ``tags``: a plate
    number changed from 京A8888 to 京A9999 kept ``["车牌号", "京A8888"]``
    (X-06, evidence ``y06b-C7-update.txt``). Two memsrv behaviours make the
    client responsible for the cleanup (probed 2026-10-29, see
    ``~/Documents/xagent-memory-saas/.probe-x06-tags-20261029/``): a PUT keeps
    whichever tags it is given
    verbatim, and an explicitly empty ``tags`` list is refilled from
    ``keywords``. So only values that were tied to the replaced text are
    dropped — a classification tag that never appeared in the body is kept.

    ``keywords`` are cleaned whenever the body changed, not only when every
    tag was removed (X-06 rework): a note whose ``tags`` were already empty
    returned early and kept ``keywords: ["京A8888"]``, which the service then
    used to refill the tag list
    (``~/Documents/xagent-memory-saas/.probe-x06-tags-20261029/probe_x06_tags3.out``).

    Returns the tags that were removed, for callers that want to report it.
    """
    old_text = _normalized_body_text(previous_content)
    new_text = _normalized_body_text(note.content)
    if old_text == new_text:
        # Nothing was replaced: leave both lists alone.
        return []

    def was_tied(value: Any) -> bool:
        text = _normalized_body_text(value)
        return bool(text) and text in old_text and text not in new_text

    tags = list(getattr(note, "tags", None) or [])
    removed = [tag for tag in tags if was_tied(tag)]
    if removed:
        note.tags = [tag for tag in tags if not was_tied(tag)]

    keywords = list(getattr(note, "keywords", None) or [])
    if any(was_tied(keyword) for keyword in keywords):
        note.keywords = [keyword for keyword in keywords if not was_tied(keyword)]
    return removed
