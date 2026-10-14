"""Model-invocable memory tools.

ReAct runs with an active memory store expose these tools so the model
manages memories itself during execution — storing valuable insights,
searching for more context, and correcting or removing stale entries —
instead of framework-driven memory pipeline steps.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

from .memory_prompts import (
    CHECK_INBOX_DESCRIPTION,
    DELETE_MEMORY_DESCRIPTION,
    DELIVER_MEMORY_DESCRIPTION,
    SEARCH_MEMORY_DESCRIPTION,
    STORE_MEMORY_DESCRIPTION,
    UPDATE_MEMORY_DESCRIPTION,
)
from ...memory.core import MemoryNote
from ...memory.remote import _unwrap_remote_store
from ..trace import (
    trace_memory_retrieve_end,
    trace_memory_retrieve_start,
    trace_memory_store_end,
    trace_memory_store_start,
)

logger = logging.getLogger(__name__)

STORE_MEMORY_TOOL_NAME = "store_memory"
SEARCH_MEMORY_TOOL_NAME = "search_memory"
UPDATE_MEMORY_TOOL_NAME = "update_memory"
DELETE_MEMORY_TOOL_NAME = "delete_memory"
DELIVER_MEMORY_TOOL_NAME = "deliver_memory"
CHECK_INBOX_TOOL_NAME = "check_inbox"
MEMORY_TOOLS_METADATA_KEY = "memory_tools_enabled"
# Cap per ReAct run. Each DAG step runs its own ReActPattern, so a DAG
# task gets a fresh cap per step rather than one shared task-wide cap.
# 2026-10-14: raised from 5 — a dense planning turn easily states six or
# more durable facts and the silent tail loss read as "auto memory forgot".
DEFAULT_MAX_STORES_PER_RUN = 20
# Cosine distance passed to search(similarity_threshold=...): lower = stricter
# dedup (fewer results count as duplicates).
DEFAULT_DEDUP_DISTANCE_THRESHOLD = 0.1
# Attachment wording refs resolve at most this cosine distance: beyond it the nearest
# note is filler, and a confident wrong quote is worse than an unresolved ref.
ATTACH_WORDING_MAX_DISTANCE = 0.60
DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 20

MemoryKind = Literal[
    "user_preference",
    "failure_pattern",
    "success_pattern",
    "tool_usage",
    "strategy",
    "domain_insight",
]
_MEMORY_KINDS = frozenset(get_args(MemoryKind))



class StoreMemoryArgs(BaseModel):
    content: str = Field(
        description=(
            "Self-contained memory text. State the insight directly; do not "
            "reference 'this task' or 'the user said above'."
        )
    )
    kind: MemoryKind = Field(
        default="domain_insight",
        description="What kind of insight this memory captures.",
    )


class StoreMemoryTool:
    """Execution-scoped ``store_memory`` tool bound to a memory store."""

    name = STORE_MEMORY_TOOL_NAME
    description = STORE_MEMORY_DESCRIPTION
    args_schema = StoreMemoryArgs

    def __init__(
        self,
        *,
        memory_store: Any,
        task: str,
        runtime: Any | None = None,
        category: str = "react_memory",
        max_stores: int = DEFAULT_MAX_STORES_PER_RUN,
        dedup_distance_threshold: float = DEFAULT_DEDUP_DISTANCE_THRESHOLD,
    ) -> None:
        self.memory_store = memory_store
        self.task = task
        self.runtime = runtime
        self.category = category
        self.max_stores = max_stores
        self.dedup_distance_threshold = dedup_distance_threshold
        self.stored_count = 0
        self._store_lock = asyncio.Lock()

    async def execute(
        self, content: str, kind: str = "domain_insight"
    ) -> dict[str, Any]:
        content = str(content or "").strip()
        if not content:
            return {
                "success": False,
                "error": "Memory content must be a non-empty string.",
            }
        if kind not in _MEMORY_KINDS:
            kind = "domain_insight"

        async with self._store_lock:
            if self.stored_count >= self.max_stores:
                return {
                    "success": False,
                    "error": (
                        f"Memory storage limit ({self.max_stores}) reached for this "
                        "task; do not store further memories."
                    ),
                }

            task_id = str(_runtime_attr(self.runtime, "execution_id") or "")
            step_id = _runtime_attr(self.runtime, "active_react_step_id")
            tracer = _runtime_attr(self.runtime, "tracer")

            if tracer is not None and task_id:
                await trace_memory_store_start(
                    tracer,
                    task_id,
                    data={
                        "task": self.task[:200],
                        "memory_category": self.category,
                        "memory_kind": kind,
                        "source": STORE_MEMORY_TOOL_NAME,
                        "step_id": step_id,
                    },
                )

            duplicate_aware = getattr(self.memory_store, "remember", None)
            if callable(duplicate_aware):
                outcome = await asyncio.to_thread(self._remember, content, kind)
                if outcome.get("unsupported"):
                    # A wrapper can expose the method while its delegate has no
                    # judged write; fall back rather than fail the store.
                    outcome = await asyncio.to_thread(
                        self._remember_locally, content, kind
                    )
            else:
                outcome = await asyncio.to_thread(self._remember_locally, content, kind)
            action = str(outcome.get("action") or "create")
            memory_id = outcome.get("memory_id")
            if outcome.get("stored"):
                # Account for the created resource before any further await so
                # trace delivery cannot reopen capacity after a cancellation.
                # A merged or attached write is still one stored fact.
                self.stored_count += 1

            if tracer is not None and task_id:
                await trace_memory_store_end(
                    tracer,
                    task_id,
                    data={
                        "storage_success": bool(outcome.get("stored")),
                        "memory_id": memory_id,
                        "storage_action": action,
                        "source": STORE_MEMORY_TOOL_NAME,
                        "step_id": step_id,
                    },
                )

            if not outcome.get("stored"):
                return {
                    "success": False,
                    "error": str(outcome.get("error") or "Failed to store memory."),
                }

            return {
                "success": True,
                "stored": True,
                "action": action,
                "memory_id": memory_id,
                **self._action_feedback(action, memory_id, outcome.get("parent_id")),
            }

    @staticmethod
    def _action_feedback(
        action: str, memory_id: Any, parent_id: Any
    ) -> dict[str, Any]:
        """Tell the model which branch the judgement took (§10.4).

        Reusing an existing memory is a success, not a skip: the caller must
        see whether the new text replaced/merged an old note or was attached
        under a related one, so it does not report "skipped as duplicate".
        """
        if action == "merge":
            return {
                "message": (
                    "Merged into an existing similar memory "
                    f"({memory_id}); the new text was combined into that note "
                    "instead of creating a duplicate."
                )
            }
        if action == "parent":
            return {
                "parent_id": parent_id,
                "message": (
                    f"Attached as a child of a related memory ({parent_id}); "
                    f"the stored note is {memory_id}."
                ),
            }
        if action == "update":
            return {
                "message": (
                    f"Updated an existing similar memory in place ({memory_id})."
                )
            }
        return {
            "message": f"Stored as a new memory ({memory_id}).",
        }

    def _remember(self, content: str, kind: str) -> dict[str, Any]:
        """Judged write through a store that offers ``remember`` (§10.4).

        The store (the remote adapter) asks the service to pick merge /
        parent / create from the candidate similarity and reports the branch
        back, so one call replaces the old "search then skip" pair.
        """
        note = MemoryNote(
            content=content,
            category=self.category,
            metadata={
                "kind": kind,
                "source": STORE_MEMORY_TOOL_NAME,
            },
        )
        try:
            response = self.memory_store.remember(note)
        except (AttributeError, NotImplementedError):
            # The store advertises the method but does not support it (a
            # wrapper over a local store); the caller falls back.
            return {"unsupported": True}
        except Exception:
            logger.exception("store_memory judged write failed")
            return {
                "stored": False,
                "action": "failed",
                "error": "Failed to store memory.",
            }
        if not getattr(response, "success", False):
            return {
                "stored": False,
                "action": "failed",
                "error": str(
                    getattr(response, "error", None) or "Failed to store memory."
                ),
            }
        response_metadata = getattr(response, "metadata", None) or {}
        return {
            "stored": True,
            "action": str(response_metadata.get("action") or "create"),
            "memory_id": getattr(response, "memory_id", None),
            "parent_id": response_metadata.get("parent_id"),
            "error": None,
        }

    def _remember_locally(self, content: str, kind: str) -> dict[str, Any]:
        """Duplicate-aware fallback for stores without a judged write.

        The local LanceDB store has no candidate scoring and no parent
        relation on a note, so a similar hit is folded into the existing note
        (an in-place update) rather than dropped: the memory is never lost,
        which is the point of the change.
        """
        existing = self._find_similar(content)
        if existing is not None:
            updated = self._merge_existing(existing, content)
            if updated:
                return {
                    "stored": True,
                    "action": "update",
                    "memory_id": getattr(existing, "id", None),
                    "parent_id": None,
                    "error": None,
                }
        memory_id = self._add(content, kind)
        if not memory_id:
            return {
                "stored": False,
                "action": "failed",
                "error": "Failed to store memory.",
            }
        return {
            "stored": True,
            "action": "create",
            "memory_id": memory_id,
            "parent_id": None,
            "error": None,
        }

    def _merge_existing(self, existing: Any, content: str) -> bool:
        """Fold new text into an existing note, keeping the visible history."""
        try:
            old_content = str(getattr(existing, "content", "") or "").strip()
            if content not in old_content:
                existing.content = (
                    f"{old_content}\n{content}" if old_content else content
                )
            response = self.memory_store.update(existing)
        except Exception:
            logger.exception("store_memory failed to merge into a similar memory")
            return False
        return bool(getattr(response, "success", False))

    def _find_similar(self, content: str) -> Any | None:
        search = getattr(self.memory_store, "search", None)
        if not callable(search):
            return None
        try:
            results = search(
                query=content,
                k=1,
                filters={"category": self.category},
                similarity_threshold=self.dedup_distance_threshold,
            )
        except Exception:
            logger.exception("store_memory dedup search failed; storing anyway")
            return None
        return results[0] if results else None

    def _add(self, content: str, kind: str) -> str | None:
        note = MemoryNote(
            content=content,
            category=self.category,
            # No request text here: it is conversation content, and a note
            # outlives the conversation it came from (#2753).
            metadata={
                "kind": kind,
                "source": STORE_MEMORY_TOOL_NAME,
            },
        )
        try:
            response = self.memory_store.add(note)
        except Exception:
            logger.exception("store_memory failed to add memory")
            return None
        if not getattr(response, "success", False):
            return None
        return getattr(response, "memory_id", None)


class SearchMemoryArgs(BaseModel):
    query: str = Field(description="What to look for in stored memories.")
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="Maximum number of memories to return.",
    )


class SearchMemoryTool:
    """Execution-scoped ``search_memory`` tool bound to a memory store."""

    name = SEARCH_MEMORY_TOOL_NAME
    description = SEARCH_MEMORY_DESCRIPTION
    args_schema = SearchMemoryArgs

    def __init__(self, *, memory_store: Any, runtime: Any | None = None) -> None:
        self.memory_store = memory_store
        self.runtime = runtime

    async def execute(
        self, query: str, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            return {"success": False, "error": "query must be a non-empty string."}
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = DEFAULT_SEARCH_LIMIT
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))

        task_id = str(_runtime_attr(self.runtime, "execution_id") or "")
        step_id = _runtime_attr(self.runtime, "active_react_step_id")
        tracer = _runtime_attr(self.runtime, "tracer")

        if tracer is not None and task_id:
            await trace_memory_retrieve_start(
                tracer,
                task_id=task_id,
                step_id=step_id,
                data={"query": query[:200], "source": SEARCH_MEMORY_TOOL_NAME},
            )

        error: str | None = None
        try:
            memories = await asyncio.to_thread(self._search, query, limit)
        except Exception:
            logger.exception("search_memory failed")
            memories = []
            error = "Failed to search memories."

        if tracer is not None and task_id:
            await trace_memory_retrieve_end(
                tracer,
                task_id=task_id,
                step_id=step_id,
                data={
                    "query": query[:200],
                    "memories_count": len(memories),
                    "found": bool(memories),
                    "success": error is None,
                    "source": SEARCH_MEMORY_TOOL_NAME,
                },
            )

        if error is not None:
            return {"success": False, "error": error}
        return {"success": True, "memories": memories, "count": len(memories)}

    def _search(self, query: str, limit: int) -> list[dict[str, Any]]:
        results = self.memory_store.search(query=query, k=limit)
        memories = []
        for note in results or []:
            content = getattr(note, "content", "") or ""
            space_kind = getattr(note, "space_kind", None)
            space_id = getattr(note, "space_id", None)
            if space_kind:
                # provenance rides with the quote: the model must know it is citing the
                # team's shared layer, not somebody's private note (§A4 hand-over form)
                tag = f"[shared:{space_kind}" + (f":{space_id}]" if space_id else "]")
                content = f"{tag} {content}"
            memories.append(
                {
                    "id": getattr(note, "id", None),
                    "content": content,
                    "category": getattr(note, "category", "general"),
                    "space_kind": space_kind,
                    "space_id": space_id,
                }
            )
        return memories


class UpdateMemoryArgs(BaseModel):
    memory_id: str = Field(
        description="Id of the memory to update, as returned by search_memory."
    )
    content: str = Field(
        description="Corrected, self-contained memory text that replaces the "
        "old content."
    )


class UpdateMemoryTool:
    """Execution-scoped ``update_memory`` tool bound to a memory store."""

    name = UPDATE_MEMORY_TOOL_NAME
    description = UPDATE_MEMORY_DESCRIPTION
    args_schema = UpdateMemoryArgs

    def __init__(self, *, memory_store: Any) -> None:
        self.memory_store = memory_store

    async def execute(self, memory_id: str, content: str) -> dict[str, Any]:
        memory_id = str(memory_id or "").strip()
        content = str(content or "").strip()
        if not memory_id or not content:
            return {
                "success": False,
                "error": "memory_id and content must be non-empty strings.",
            }
        return await asyncio.to_thread(self._update, memory_id, content)

    def _update(self, memory_id: str, content: str) -> dict[str, Any]:
        try:
            existing = self.memory_store.get(memory_id)
            if not getattr(existing, "success", False):
                return {
                    "success": False,
                    "error": (
                        f"Memory '{memory_id}' not found or not accessible (it may "
                        "exist under another owner). Do not tell the user it was "
                        "never recorded — search first, then ask whether the id is "
                        "right."
                    ),
                }
            note = getattr(existing, "content", None)
            if note is None:
                return {
                    "success": False,
                    "error": f"Memory '{memory_id}' has no stored note to update.",
                }
            note.content = content
            if note.metadata is None:
                note.metadata = {}
            response = self.memory_store.update(note)
        except Exception:
            logger.exception("update_memory failed")
            return {"success": False, "error": "Failed to update memory."}
        if not getattr(response, "success", False):
            return {
                "success": False,
                "error": str(getattr(response, "error", None) or "Update failed."),
            }
        return {"success": True, "memory_id": memory_id}


class DeleteMemoryArgs(BaseModel):
    memory_id: str = Field(
        description="Id of the memory to delete, as returned by search_memory."
    )


class DeleteMemoryTool:
    """Execution-scoped ``delete_memory`` tool bound to a memory store."""

    name = DELETE_MEMORY_TOOL_NAME
    description = DELETE_MEMORY_DESCRIPTION
    args_schema = DeleteMemoryArgs

    def __init__(self, *, memory_store: Any) -> None:
        self.memory_store = memory_store

    async def execute(self, memory_id: str) -> dict[str, Any]:
        memory_id = str(memory_id or "").strip()
        if not memory_id:
            return {"success": False, "error": "memory_id must be a non-empty string."}
        return await asyncio.to_thread(self._delete, memory_id)

    def _delete(self, memory_id: str) -> dict[str, Any]:
        try:
            response = self.memory_store.delete(memory_id)
        except Exception:
            logger.exception("delete_memory failed")
            return {"success": False, "error": "Failed to delete memory."}
        if not getattr(response, "success", False):
            return {
                "success": False,
                "error": str(getattr(response, "error", None) or "Delete failed."),
            }
        return {"success": True, "memory_id": memory_id}


class DeliverMemoryArgs(BaseModel):
    target: str = Field(
        description=(
            "Who receives it: a teammate's username, external id or agent "
            "name, for example t10-probe."
        )
    )
    content: str = Field(
        description=(
            "The note to hand over — one self-contained statement, the same "
            "shape as store_memory content."
        )
    )
    attach: list[str] = Field(
        default_factory=list,
        description=(
            "Memories to ride along as quoted attachments: memory ids when "
            "you have them, or short keywords to look them up. The quoted "
            "text is appended to the delivery so the recipient can read it "
            "without a second lookup — treat it like quoting a document in a "
            "message."
        ),
    )


class DeliverMemoryTool:
    """Execution-scoped ``deliver_memory`` tool bound to a memory store."""

    name = DELIVER_MEMORY_TOOL_NAME
    description = DELIVER_MEMORY_DESCRIPTION
    args_schema = DeliverMemoryArgs

    def __init__(self, *, memory_store: Any) -> None:
        self.memory_store = memory_store

    async def execute(
        self, target: str, content: str, attach: list[str] | None = None
    ) -> dict[str, Any]:
        target = str(target or "").strip()
        content = str(content or "").strip()
        if not target:
            return {
                "success": False,
                "error": "target must be a non-empty recipient id.",
            }
        if not content:
            return {
                "success": False,
                "error": "content must be a non-empty statement.",
            }
        # production hands this tool a wrapper chain (revocation / user isolation)
        # over the real adapter — a class-name check would always miss it, the
        # same trap that broke the seat override (bounded unwrap instead).
        if _unwrap_remote_store(self.memory_store) is None:
            return {
                "success": False,
                "error": (
                    "delivery needs the remote memory service; the active "
                    "store has no teammate inbox."
                ),
            }
        quoted, unresolved = await self._quote_attachments(attach or [])
        if quoted:
            content = f"{content}\n\n— attached memories —\n{quoted}"
        note = MemoryNote(content=f"[to:{target}] {content}")
        try:
            response = await asyncio.to_thread(self.memory_store.add, note)
        except Exception:
            logger.exception("deliver_memory failed")
            return {"success": False, "error": "Failed to deliver the note."}
        if not getattr(response, "success", False):
            return {
                "success": False,
                "error": str(getattr(response, "error", None) or "Delivery failed."),
            }
        result = {
            "success": True,
            "memory_id": getattr(response, "memory_id", None),
            "delivered_to": target,
            "attachments_quoted": (len(attach or []) - len(unresolved)),
        }
        if unresolved:
            # the sender must SEE the stale refs: silently swapping in whatever was
            # nearest turned a broken quote into a confident wrong one
            result["attachments_unresolved"] = unresolved
        return result

    async def _quote_attachments(self, refs: list[str]) -> tuple[str, list[str]]:
        """Resolve each attachment ref into quoted memory text.

        A ref that looks like an id is fetched directly and never fuzzy-matched — an id
        that no longer exists (or that the sender may not read) must surface as
        unresolved, not resolve to whatever note happens to be nearest. Wording refs
        search with a relevance ceiling so a near-miss comes back unresolved too.
        Unresolvable refs are skipped rather than failing the delivery — a message with
        a stale quote still carries its own text.
        """
        lines: list[str] = []
        seen: set[str] = set()
        unresolved: list[str] = []
        for ref in list(refs)[:8]:
            ref = str(ref or "").strip()
            if not ref or ref in seen:
                continue
            seen.add(ref)
            note = None
            if len(ref) >= 32 and "-" in ref:
                get = getattr(self.memory_store, "get", None)
                if not callable(get):
                    unresolved.append(ref)
                    continue
                try:
                    response = await asyncio.to_thread(get, ref)
                    if getattr(response, "success", False):
                        candidate = getattr(response, "content", None)
                        if candidate is not None:
                            note = candidate
                except Exception:
                    logger.debug("attachment id lookup failed", exc_info=True)
                if note is None:
                    # an id ref is either gone or invisible: both mean "quote not found"
                    unresolved.append(ref)
                    continue
            if note is None:
                search = getattr(self.memory_store, "search", None)
                if callable(search):
                    try:
                        results = await asyncio.to_thread(
                            lambda: search(
                                query=ref,
                                k=1,
                                similarity_threshold=ATTACH_WORDING_MAX_DISTANCE,
                            )
                        )
                        note = results[0] if results else None
                    except Exception:
                        logger.debug("attachment keyword lookup failed", exc_info=True)
            if note is None:
                unresolved.append(ref)
                continue
            text = str(getattr(note, "content", "") or "").strip()
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines), unresolved


class CheckInboxArgs(BaseModel):
    limit: int = Field(
        default=20,
        description="How many of the most recent deliveries to return (1-50).",
    )


class CheckInboxTool:
    """Execution-scoped ``check_inbox`` tool bound to a memory store."""

    name = CHECK_INBOX_TOOL_NAME
    description = CHECK_INBOX_DESCRIPTION
    args_schema = CheckInboxArgs

    def __init__(self, *, memory_store: Any) -> None:
        self.memory_store = memory_store

    async def execute(self, limit: int = 20) -> dict[str, Any]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 50))
        # Prefer the dedicated inbox surface (unread-first + receipts beside the
        # immutable delivery). Legacy/fake stores without it keep the list+filter path.
        inbox_list = getattr(self.memory_store, "inbox_list", None)
        if callable(inbox_list):
            try:
                notes = await asyncio.to_thread(lambda: inbox_list(include_read=False))
            except Exception:
                logger.exception("check_inbox failed")
                return {"success": False, "error": "Failed to read the inbox."}
            ordered = sorted(
                notes, key=lambda n: str(getattr(n, "timestamp", "") or ""), reverse=True
            )
            shown = ordered[:limit]
            items = []
            for note in shown:
                metadata = getattr(note, "metadata", None) or {}
                items.append(
                    {
                        "id": getattr(note, "id", None),
                        "content": str(getattr(note, "content", "") or ""),
                        "from_user": metadata.get("from_user"),
                        "timestamp": str(getattr(note, "timestamp", "") or ""),
                    }
                )
            marked = 0
            inbox_read = getattr(self.memory_store, "inbox_read", None)
            ids = [i["id"] for i in items if i.get("id")]
            if ids and callable(inbox_read):
                try:
                    marked = await asyncio.to_thread(lambda: inbox_read(ids))
                except Exception:
                    # receipts are best effort: the deliveries were still returned
                    logger.warning("check_inbox could not take receipts", exc_info=True)
            result = {
                "success": True,
                "count": len(items),
                "deliveries": items,
                "marked_read": marked,
                "unread_remaining": max(0, len(ordered) - len(shown)),
            }
            return result
        list_all = getattr(self.memory_store, "list_all", None)
        if not callable(list_all):
            return {
                "success": False,
                "error": "the active memory store cannot list an inbox.",
            }
        try:
            notes = await asyncio.to_thread(
                list_all, {"metadata": {"deliver": True}}
            )
        except Exception:
            logger.exception("check_inbox failed")
            return {"success": False, "error": "Failed to read the inbox."}
        ordered = sorted(
            notes, key=lambda n: str(getattr(n, "timestamp", "") or ""), reverse=True
        )
        items = []
        for note in ordered[:limit]:
            metadata = getattr(note, "metadata", None) or {}
            items.append(
                {
                    "id": getattr(note, "id", None),
                    "content": str(getattr(note, "content", "") or ""),
                    "from_user": metadata.get("from_user"),
                    "timestamp": str(getattr(note, "timestamp", "") or ""),
                }
            )
        return {"success": True, "count": len(items), "deliveries": items}


def build_store_memory_tool(
    *,
    memory_store: Any | None,
    task: str,
    runtime: Any | None = None,
    category: str = "react_memory",
) -> StoreMemoryTool | None:
    """Create a ``store_memory`` tool, or None when no memory store is active."""

    if memory_store is None:
        return None
    return StoreMemoryTool(
        memory_store=memory_store,
        task=task,
        runtime=runtime,
        category=category,
    )


def build_memory_tools(
    *,
    memory_store: Any | None,
    task: str,
    runtime: Any | None = None,
    context: Any | None = None,
) -> list[Any]:
    """Create the memory tool set, or [] when no memory store is active.

    When ``context`` is given, mark it so the system context renders the
    memory-usage guidance alongside the tools (see
    ``MEMORY_TOOLS_METADATA_KEY``).
    """

    if memory_store is None:
        return []
    tools: list[Any] = [
        StoreMemoryTool(memory_store=memory_store, task=task, runtime=runtime),
        SearchMemoryTool(memory_store=memory_store, runtime=runtime),
        UpdateMemoryTool(memory_store=memory_store),
        DeleteMemoryTool(memory_store=memory_store),
        DeliverMemoryTool(memory_store=memory_store),
        CheckInboxTool(memory_store=memory_store),
    ]
    if tools and context is not None and hasattr(context, "metadata"):
        context.metadata[MEMORY_TOOLS_METADATA_KEY] = True
    return tools


def _runtime_attr(runtime: Any | None, name: str) -> Any | None:
    if runtime is None:
        return None
    return getattr(runtime, name, None)
