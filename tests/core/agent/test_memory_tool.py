"""Tests for the model-invocable ``store_memory`` tool."""

import asyncio
import json
from datetime import datetime
from typing import Any

import pytest
import requests

from xagent.core.agent.context.memory_tool import (
    CheckInboxTool,
    DeleteMemoryTool,
    DeliverMemoryTool,
    SearchMemoryArgs,
    SearchMemoryTool,
    StoreMemoryTool,
    UpdateMemoryTool,
    build_memory_tools,
    build_store_memory_tool,
)
from xagent.core.memory.core import MemoryNote, MemoryResponse
from xagent.core.memory.lancedb import LanceDBMemoryStore
from xagent.core.memory.remote import RemoteMemoryStore, RemoteMemoryStoreError
from xagent.web.memory_lifecycle import MemoryLifecycleState, MemoryLifecycleStatus
from xagent.web.revocable_memory_store import RevocableMemoryStore
from xagent.web.user_isolated_memory import UserIsolatedMemoryStore

SERVICE_URL = "http://memsrv:8080"
SERVICE_KEY = "svc-key"


class RecordingMemoryStore:
    def __init__(
        self,
        *,
        search_results: list[Any] | None = None,
        add_success: bool = True,
    ) -> None:
        self.search_results = search_results or []
        self.add_success = add_success
        self.searches: list[dict[str, Any]] = []
        self.added: list[MemoryNote] = []

    def search(self, **kwargs: Any) -> list[Any]:
        self.searches.append(kwargs)
        return list(self.search_results)

    def add(self, note: MemoryNote) -> MemoryResponse:
        self.added.append(note)
        if not self.add_success:
            return MemoryResponse(success=False, error="boom")
        return MemoryResponse(success=True, memory_id=f"mem-{len(self.added)}")


class TraceEventRecorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def trace_event(
        self,
        event_type: Any,
        *,
        task_id: str | None = None,
        step_id: str | None = None,
        data: dict[str, Any] | None = None,
        **_: Any,
    ) -> str:
        self.events.append(
            {
                "event_type": getattr(event_type, "value", str(event_type)),
                "task_id": task_id,
                "data": data or {},
            }
        )
        return str(len(self.events))


class FakeRuntime:
    def __init__(self, tracer: Any | None = None) -> None:
        self.tracer = tracer
        self.execution_id = "task-1"
        self.active_react_step_id = "react_step_1"


@pytest.mark.asyncio
async def test_store_memory_adds_note_with_metadata() -> None:
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(memory_store=store, task="Fix the deploy pipeline")

    result = await tool.execute(
        content="User prefers reports in Chinese.", kind="user_preference"
    )

    assert result == {
        "success": True,
        "stored": True,
        "action": "create",
        "memory_id": "mem-1",
        "message": "Stored as a new memory (mem-1).",
    }
    note = store.added[0]
    assert note.content == "User prefers reports in Chinese."
    assert note.category == "react_memory"
    # The user's request text is conversation content and must not outlive a
    # purged conversation inside the memory store (#2753).
    assert note.metadata == {"kind": "user_preference", "source": "store_memory"}
    assert tool.stored_count == 1


@pytest.mark.asyncio
async def test_store_memory_merges_into_a_similar_note() -> None:
    """A similar hit is folded into the existing note, never dropped.

    The old behaviour skipped the write ("stored": false) and lost the new
    fact; the judged path keeps both by updating the note in place.
    """
    store = CrudMemoryStore({"mem-1": _note("mem-1", "Same insight.")})
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="Same insight, refined.")

    assert result["success"] is True
    assert result["stored"] is True
    assert result["action"] == "update"
    assert store.updated[0].id == "mem-1"
    assert "Same insight, refined." in str(store.updated[0].content)
    assert store.searches[0]["filters"] == {"category": "react_memory"}
    assert tool.stored_count == 1


@pytest.mark.asyncio
async def test_store_memory_enforces_per_run_quota() -> None:
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(memory_store=store, task="task", max_stores=2)

    assert (await tool.execute(content="First insight."))["success"] is True
    assert (await tool.execute(content="Second insight."))["success"] is True
    result = await tool.execute(content="Third insight.")

    assert result["success"] is False
    assert "limit" in result["error"]
    assert len(store.added) == 2


@pytest.mark.asyncio
async def test_store_memory_serializes_concurrent_quota_checks() -> None:
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(memory_store=store, task="task", max_stores=1)

    results = await asyncio.gather(
        tool.execute(content="First concurrent insight."),
        tool.execute(content="Second concurrent insight."),
    )

    assert sum(result.get("stored") is True for result in results) == 1
    assert sum("limit" in result.get("error", "") for result in results) == 1
    assert len(store.added) == 1
    assert tool.stored_count == 1


@pytest.mark.asyncio
async def test_store_memory_rejects_empty_content() -> None:
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="   ")

    assert result["success"] is False
    assert store.added == []


@pytest.mark.asyncio
async def test_store_memory_normalizes_unknown_kind() -> None:
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="An insight.", kind="made_up_kind")

    assert result["success"] is True
    assert store.added[0].metadata["kind"] == "domain_insight"


@pytest.mark.asyncio
async def test_store_memory_reports_add_failure() -> None:
    store = RecordingMemoryStore(add_success=False)
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="An insight.")

    assert result["success"] is False
    assert tool.stored_count == 0


@pytest.mark.asyncio
async def test_store_memory_emits_store_trace_events() -> None:
    tracer = TraceEventRecorder()
    store = RecordingMemoryStore()
    tool = StoreMemoryTool(
        memory_store=store,
        task="task",
        runtime=FakeRuntime(tracer=tracer),
    )

    await tool.execute(content="An insight.")

    event_types = [event["event_type"] for event in tracer.events]
    assert event_types == ["task_start_memory_store", "task_end_memory_store"]
    assert all(event["task_id"] == "task-1" for event in tracer.events)
    assert tracer.events[1]["data"]["storage_success"] is True
    assert tracer.events[1]["data"]["memory_id"] == "mem-1"


@pytest.mark.asyncio
async def test_store_memory_stores_when_dedup_search_fails() -> None:
    class BrokenSearchStore(RecordingMemoryStore):
        def search(self, **kwargs: Any) -> list[Any]:
            raise RuntimeError("search unavailable")

    store = BrokenSearchStore()
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="An insight.")

    assert result["success"] is True
    assert len(store.added) == 1


def test_build_store_memory_tool_requires_store() -> None:
    assert build_store_memory_tool(memory_store=None, task="task") is None
    tool = build_store_memory_tool(memory_store=RecordingMemoryStore(), task="task")
    assert isinstance(tool, StoreMemoryTool)
    assert tool.name == "store_memory"


class CrudMemoryStore(RecordingMemoryStore):
    """Recording store with get/update/delete for the CRUD tools."""

    def __init__(self, notes: dict[str, MemoryNote] | None = None) -> None:
        super().__init__()
        self.notes = dict(notes or {})
        self.updated: list[MemoryNote] = []
        self.deleted: list[str] = []

    def search(self, **kwargs: Any) -> list[Any]:
        self.searches.append(kwargs)
        return list(self.notes.values())

    def get(self, note_id: str) -> MemoryResponse:
        note = self.notes.get(note_id)
        if note is None:
            return MemoryResponse(success=False, error="Note not found")
        return MemoryResponse(success=True, memory_id=note_id, content=note)

    def update(self, note: MemoryNote) -> MemoryResponse:
        self.updated.append(note)
        self.notes[note.id] = note
        return MemoryResponse(success=True, memory_id=note.id)

    def delete(self, note_id: str) -> MemoryResponse:
        if note_id not in self.notes:
            return MemoryResponse(success=False, error="Note not found")
        del self.notes[note_id]
        self.deleted.append(note_id)
        return MemoryResponse(success=True, memory_id=note_id)


def _note(note_id: str, content: str) -> MemoryNote:
    return MemoryNote(id=note_id, content=content, category="react_memory")


@pytest.mark.asyncio
async def test_search_memory_returns_ids_and_content() -> None:
    store = CrudMemoryStore({"mem-1": _note("mem-1", "User prefers Chinese.")})
    tool = SearchMemoryTool(memory_store=store)

    result = await tool.execute(query="preferences")

    assert result["success"] is True
    assert result["count"] == 1
    assert result["memories"] == [
        {
            "id": "mem-1",
            "content": "User prefers Chinese.",
            "category": "react_memory",
            "space_kind": None,
            "space_id": None,
        }
    ]
    assert store.searches[0]["query"] == "preferences"


@pytest.mark.asyncio
async def test_search_memory_rejects_empty_query_and_emits_trace() -> None:
    tracer = TraceEventRecorder()
    store = CrudMemoryStore()
    tool = SearchMemoryTool(memory_store=store, runtime=FakeRuntime(tracer=tracer))

    empty = await tool.execute(query="  ")
    ok = await tool.execute(query="anything")

    assert empty["success"] is False
    assert ok["success"] is True
    event_types = [event["event_type"] for event in tracer.events]
    assert event_types == [
        "task_start_memory_retrieve",
        "task_end_memory_retrieve",
    ]
    assert tracer.events[-1]["data"]["success"] is True


@pytest.mark.asyncio
async def test_search_memory_reports_backend_failure() -> None:
    class BrokenSearchStore(CrudMemoryStore):
        def search(self, **kwargs: Any) -> list[Any]:
            raise RuntimeError("backend unavailable")

    tracer = TraceEventRecorder()
    tool = SearchMemoryTool(
        memory_store=BrokenSearchStore(), runtime=FakeRuntime(tracer=tracer)
    )

    result = await tool.execute(query="preferences")

    # P1-4: the raised error's own message is surfaced to the model instead of
    # a generic string that hides what failed.
    assert result == {"success": False, "error": "backend unavailable"}
    assert tracer.events[-1]["data"]["success"] is False
    assert tracer.events[-1]["data"]["found"] is False


@pytest.mark.asyncio
async def test_search_memory_reports_terminal_lancedb_failure(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenConnection:
        def open_table(self, _: str) -> Any:
            raise RuntimeError("memory table unavailable")

    base_store = LanceDBMemoryStore(
        db_dir=str(tmp_path),
        collection_name="terminal_failure",
    )
    monkeypatch.setattr(
        base_store._vector_store,
        "get_raw_connection",
        lambda: BrokenConnection(),
    )
    tool = SearchMemoryTool(
        memory_store=UserIsolatedMemoryStore(base_store),
    )

    result = await tool.execute(query="preferences")

    # P1-4: the propagated message is the user-facing error (str(e), no
    # traceback), so the exact text now follows the exception.
    assert result["success"] is False
    assert "memory table unavailable" in result["error"]


@pytest.mark.asyncio
async def test_update_memory_replaces_content() -> None:
    store = CrudMemoryStore({"mem-1": _note("mem-1", "Old fact.")})
    tool = UpdateMemoryTool(memory_store=store)

    result = await tool.execute(memory_id="mem-1", content="Corrected fact.")

    assert result == {"success": True, "memory_id": "mem-1"}
    assert store.updated[0].content == "Corrected fact."
    # No request text is stamped onto the rewritten note (#2753).
    assert store.updated[0].metadata == {}


@pytest.mark.asyncio
async def test_update_memory_initializes_missing_metadata() -> None:
    note = _note("mem-1", "Old fact.")
    note.metadata = None  # type: ignore[assignment]
    store = CrudMemoryStore({"mem-1": note})
    tool = UpdateMemoryTool(memory_store=store)

    result = await tool.execute(memory_id="mem-1", content="Corrected fact.")

    assert result == {"success": True, "memory_id": "mem-1"}
    assert store.updated[0].metadata == {}


@pytest.mark.asyncio
async def test_update_memory_reports_missing_note_and_bad_args() -> None:
    store = CrudMemoryStore()
    tool = UpdateMemoryTool(memory_store=store)

    missing = await tool.execute(memory_id="nope", content="New text.")
    bad = await tool.execute(memory_id="", content="")

    assert missing["success"] is False
    assert "not found" in missing["error"]
    assert bad["success"] is False
    assert store.updated == []


@pytest.mark.asyncio
async def test_delete_memory_removes_note() -> None:
    store = CrudMemoryStore({"mem-1": _note("mem-1", "Wrong fact.")})
    tool = DeleteMemoryTool(memory_store=store)

    result = await tool.execute(memory_id="mem-1")
    missing = await tool.execute(memory_id="mem-1")

    assert result == {"success": True, "memory_id": "mem-1"}
    assert store.deleted == ["mem-1"]
    assert missing["success"] is False


def test_build_memory_tools_composition() -> None:
    assert build_memory_tools(memory_store=None, task="task") == []
    tools = build_memory_tools(memory_store=CrudMemoryStore(), task="task")
    assert [tool.name for tool in tools] == [
        "store_memory",
        "search_memory",
        "update_memory",
        "delete_memory",
        # T14 team channel: directed delivery plus the recipient's inbox reader
        "deliver_memory",
        "check_inbox",
    ]


@pytest.mark.asyncio
async def test_update_memory_reports_note_without_content() -> None:
    class NoContentStore(CrudMemoryStore):
        def get(self, note_id: str) -> MemoryResponse:
            return MemoryResponse(success=True, memory_id=note_id, content=None)

    tool = UpdateMemoryTool(memory_store=NoContentStore())

    result = await tool.execute(memory_id="mem-1", content="New text.")

    assert result["success"] is False
    assert "no stored note" in result["error"]


def test_build_memory_tools_stamps_guidance_flag_on_context() -> None:
    class Ctx:
        def __init__(self) -> None:
            self.metadata: dict[str, Any] = {}

    context = Ctx()
    tools = build_memory_tools(
        memory_store=RecordingMemoryStore(), task="task", context=context
    )

    assert tools
    assert context.metadata["memory_tools_enabled"] is True

    disabled_context = Ctx()
    assert (
        build_memory_tools(memory_store=None, task="task", context=disabled_context)
        == []
    )
    assert "memory_tools_enabled" not in disabled_context.metadata


@pytest.mark.asyncio
async def test_search_memory_coerces_invalid_limit() -> None:
    store = RecordingMemoryStore()
    tool = SearchMemoryTool(memory_store=store)

    result = await tool.execute(query="anything", limit="lots")  # type: ignore[arg-type]

    assert result["success"] is True
    assert store.searches[0]["k"] == 5


@pytest.mark.asyncio
async def test_store_memory_falls_back_when_the_judged_write_is_unsupported() -> None:
    """A wrapper exposing ``remember`` over a local store must not fail the write."""

    class UnsupportedRememberStore(RecordingMemoryStore):
        def remember(self, note: MemoryNote) -> MemoryResponse:
            raise AttributeError("memory store does not support remember")

    store = UnsupportedRememberStore()
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="An insight.")

    assert result["success"] is True
    assert result["action"] == "create"
    assert len(store.added) == 1


class JudgedMemoryStore(RecordingMemoryStore):
    """Store exposing the judged ``remember`` write of the remote adapter."""

    def __init__(
        self, *, action: str, parent_id: str | None = None, success: bool = True
    ) -> None:
        super().__init__()
        self.action = action
        self.parent_id = parent_id
        self.success = success
        self.remembered: list[MemoryNote] = []

    def remember(self, note: MemoryNote) -> MemoryResponse:
        self.remembered.append(note)
        if not self.success:
            return MemoryResponse(success=False, error="judged write refused")
        return MemoryResponse(
            success=True,
            memory_id="mem-judged",
            metadata={"action": self.action, "parent_id": self.parent_id},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "parent_id", "message_fragment"),
    [
        ("merge", None, "Merged into an existing similar memory"),
        ("parent", "mem-parent", "Attached as a child of a related memory"),
        ("create", None, "Stored as a new memory"),
    ],
)
async def test_store_memory_dispatches_the_judged_branch(
    action: str, parent_id: str | None, message_fragment: str
) -> None:
    """All three branches of the judged write are reported, none is dropped."""
    store = JudgedMemoryStore(action=action, parent_id=parent_id)
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="A durable business fact.")

    assert result["success"] is True
    assert result["stored"] is True
    assert result["action"] == action
    assert result["memory_id"] == "mem-judged"
    assert message_fragment in result["message"]
    assert store.remembered[0].content == "A durable business fact."
    assert store.remembered[0].metadata["source"] == "store_memory"
    if action == "parent":
        assert result["parent_id"] == "mem-parent"
    assert tool.stored_count == 1


@pytest.mark.asyncio
async def test_store_memory_reports_a_failed_judged_write() -> None:
    store = JudgedMemoryStore(action="create", success=False)
    tool = StoreMemoryTool(memory_store=store, task="task")

    result = await tool.execute(content="A durable fact.")

    assert result["success"] is False
    assert result["error"] == "judged write refused"
    assert tool.stored_count == 0
    assert store.added == []


@pytest.mark.asyncio
async def test_store_memory_emits_the_branch_in_the_store_trace() -> None:
    tracer = TraceEventRecorder()
    store = JudgedMemoryStore(action="parent", parent_id="mem-parent")
    tool = StoreMemoryTool(
        memory_store=store, task="task", runtime=FakeRuntime(tracer=tracer)
    )

    await tool.execute(content="A durable fact.")

    assert tracer.events[-1]["data"]["storage_action"] == "parent"
    assert tracer.events[-1]["data"]["storage_success"] is True


# ---------------------------------------------------------------------------
# check_inbox: the dedicated inbox surface behind the wrapper chain (P0-1)
# ---------------------------------------------------------------------------


def _delivery(note_id: str, content: str, at: str, from_user: int) -> MemoryNote:
    return MemoryNote(
        id=note_id,
        content=content,
        category="general",
        timestamp=datetime.fromisoformat(at),
        metadata={"deliver": True, "from_user": from_user},
    )


def _inbox_notes() -> list[MemoryNote]:
    return [
        _delivery("d1", "first", "2026-10-15T09:00:00", 7),
        _delivery("d2", "second", "2026-10-15T10:00:00", 8),
        _delivery("d3", "third", "2026-10-15T11:00:00", 9),
    ]


class InboxSurfaceStore:
    """Fake exposing the dedicated inbox surface (unread list + receipts)."""

    def __init__(self) -> None:
        self.notes = _inbox_notes()
        self.inbox_calls: list[bool] = []
        self.read_ids: list[str] = []
        self.list_all_calls: list[Any] = []

    def inbox_list(self, include_read: bool = False) -> list[MemoryNote]:
        self.inbox_calls.append(include_read)
        return list(self.notes)

    def inbox_read(self, ids: list[str]) -> int:
        self.read_ids = list(ids)
        return len(ids)

    def list_all(self, filters: Any = None) -> list[MemoryNote]:
        self.list_all_calls.append(filters)
        raise AssertionError("legacy list_all must not run when the surface exists")


class LegacyInboxStore:
    """Fake without the dedicated surface: only the legacy list path exists."""

    def __init__(self) -> None:
        self.notes = _inbox_notes()
        self.list_all_calls: list[Any] = []

    def list_all(self, filters: Any = None) -> list[MemoryNote]:
        self.list_all_calls.append(filters)
        return list(self.notes)


class _ScriptedSession:
    """Fake HTTP transport: scripted ``(status, payload)`` answers in order."""

    def __init__(self, *responses: tuple[int, Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        status, payload = self._responses.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(payload).encode("utf-8")
        response.headers["Content-Type"] = "application/json"
        return response


class _WrappedRemoteStore:
    """A wrapper that does not forward the inbox surface, adapter behind it."""

    def __init__(self, remote: RemoteMemoryStore) -> None:
        self._base_store = remote
        self.list_all_calls: list[Any] = []
        self.added: list[MemoryNote] = []

    def list_all(self, filters: Any = None) -> list[MemoryNote]:
        self.list_all_calls.append(filters)
        return [_delivery("d1", "legacy", "2026-10-15T09:00:00", 7)]

    def add(self, note: MemoryNote) -> MemoryResponse:
        self.added.append(note)
        raise RemoteMemoryStoreError(
            "Remote memory service returned HTTP 409: /v1/memory/deliver"
            " — you already delivered this note;"
            " send a follow-up delivery instead",
            status_code=409,
        )


class _PublicationSource:
    """Minimal publication source for the revocable wrapper (test double)."""

    def __init__(self, generation: int = 1) -> None:
        self.generation = generation

    def publication_generation(self) -> int:
        return self.generation

    def published_status(self) -> MemoryLifecycleStatus:
        return MemoryLifecycleStatus(state=MemoryLifecycleState.RESTART_REQUIRED)


@pytest.mark.asyncio
async def test_check_inbox_walks_the_wrapper_to_the_dedicated_surface() -> None:
    """A wrapper store must not hide the surface: unread filter + receipts."""
    base = InboxSurfaceStore()
    tool = CheckInboxTool(memory_store=UserIsolatedMemoryStore(base))

    result = await tool.execute(limit=2)

    assert result["success"] is True
    assert [d["id"] for d in result["deliveries"]] == ["d3", "d2"]
    assert result["count"] == 2
    assert result["marked_read"] == 2
    assert result["unread_remaining"] == 1
    assert base.read_ids == ["d3", "d2"]
    assert base.inbox_calls == [False]
    # the legacy path must not be taken when the surface exists
    assert base.list_all_calls == []


@pytest.mark.asyncio
async def test_check_inbox_through_the_full_production_chain() -> None:
    """Revocable(user_isolated(remote)): live reads go over the inbox routes,
    and a revoked reference fails closed instead of reaching the adapter."""
    session = _ScriptedSession(
        (
            200,
            [
                {
                    "id": "d1",
                    "content": "hello",
                    "category": "general",
                    "timestamp": "2026-10-15T10:00:00",
                    "metadata": {"from_user": 7},
                }
            ],
        ),
        (200, {"marked": 1}),
    )
    remote = RemoteMemoryStore(SERVICE_URL, SERVICE_KEY, session=session)
    source = _PublicationSource(generation=1)
    store = RevocableMemoryStore(  # type: ignore[arg-type]
        UserIsolatedMemoryStore(remote), source, generation=1
    )
    tool = CheckInboxTool(memory_store=store)

    live = await tool.execute()

    assert live["success"] is True
    assert [d["id"] for d in live["deliveries"]] == ["d1"]
    assert live["marked_read"] == 1
    assert live["unread_remaining"] == 0
    assert [call["url"] for call in session.calls] == [
        f"{SERVICE_URL}/v1/memory/inbox/list",
        f"{SERVICE_URL}/v1/memory/inbox/read",
    ]

    source.generation = 2  # the manager revoked this publication

    revoked = await tool.execute()

    assert revoked["success"] is False
    # the revoked reference never reached the adapter: no third request
    assert len(session.calls) == 2


@pytest.mark.asyncio
async def test_check_inbox_reaches_the_adapter_behind_a_hiding_wrapper() -> None:
    """A wrapper without forwarding methods must not hide the capability."""
    session = _ScriptedSession(
        (
            200,
            [
                {
                    "id": "d1",
                    "content": "hello",
                    "category": "general",
                    "timestamp": "2026-10-15T10:00:00",
                    "metadata": {"from_user": 7},
                }
            ],
        ),
        (200, {"marked": 1}),
    )
    wrapper = _WrappedRemoteStore(
        RemoteMemoryStore(SERVICE_URL, SERVICE_KEY, session=session)
    )
    tool = CheckInboxTool(memory_store=wrapper)

    result = await tool.execute()

    assert result["success"] is True
    assert [d["id"] for d in result["deliveries"]] == ["d1"]
    assert result["marked_read"] == 1
    assert result["unread_remaining"] == 0
    assert wrapper.list_all_calls == []
    assert [call["url"] for call in session.calls] == [
        f"{SERVICE_URL}/v1/memory/inbox/list",
        f"{SERVICE_URL}/v1/memory/inbox/read",
    ]


@pytest.mark.asyncio
async def test_check_inbox_falls_back_to_legacy_on_a_missing_inbox_route() -> None:
    """An old service answers 404 for the inbox routes: use the legacy path."""
    session = _ScriptedSession((404, {"error": {"message": "no such route"}}))
    wrapper = _WrappedRemoteStore(
        RemoteMemoryStore(SERVICE_URL, SERVICE_KEY, session=session)
    )
    tool = CheckInboxTool(memory_store=wrapper)

    result = await tool.execute()

    assert result["success"] is True
    assert [d["id"] for d in result["deliveries"]] == ["d1"]
    # legacy shape: no receipt bookkeeping, no unread counter
    assert "unread_remaining" not in result
    assert "marked_read" not in result
    assert wrapper.list_all_calls == [{"metadata": {"deliver": True}}]
    assert session.calls[0]["url"] == f"{SERVICE_URL}/v1/memory/inbox/list"


@pytest.mark.asyncio
async def test_check_inbox_falls_back_to_legacy_when_the_delegate_lacks_it() -> None:
    """A forwarding wrapper over a local store raises AttributeError → legacy."""
    base = LegacyInboxStore()
    tool = CheckInboxTool(memory_store=UserIsolatedMemoryStore(base))

    result = await tool.execute()

    assert result["success"] is True
    assert result["count"] == 3
    assert "unread_remaining" not in result
    assert base.list_all_calls == [{"metadata": {"deliver": True}}]


@pytest.mark.asyncio
async def test_check_inbox_keeps_the_legacy_path_for_surface_less_fakes() -> None:
    """A plain fake store with only list_all keeps the historical behaviour."""
    base = LegacyInboxStore()
    tool = CheckInboxTool(memory_store=base)

    result = await tool.execute(limit=2)

    assert result == {
        "success": True,
        "count": 2,
        "deliveries": [
            {
                "id": "d3",
                "content": "third",
                "from_user": 9,
                "timestamp": "2026-10-15 11:00:00",
            },
            {
                "id": "d2",
                "content": "second",
                "from_user": 8,
                "timestamp": "2026-10-15 10:00:00",
            },
        ],
    }
    assert base.list_all_calls == [{"metadata": {"deliver": True}}]


# ---------------------------------------------------------------------------
# server-side error messages reach the model (P1-4)
# ---------------------------------------------------------------------------

APPEND_ONLY_409 = (
    "Remote memory service returned HTTP 409: /v1/memory/notes/mem-1"
    " — this note is append-only; send a follow-up delivery instead"
)


@pytest.mark.asyncio
async def test_update_memory_surfaces_the_service_message() -> None:
    class AppendOnlyStore(CrudMemoryStore):
        def update(self, note: MemoryNote) -> MemoryResponse:
            raise RemoteMemoryStoreError(APPEND_ONLY_409, status_code=409)

    store = AppendOnlyStore({"mem-1": _note("mem-1", "Delivered note.")})
    tool = UpdateMemoryTool(memory_store=store)

    result = await tool.execute(memory_id="mem-1", content="Corrected fact.")

    assert result["success"] is False
    assert "send a follow-up delivery instead" in result["error"]


@pytest.mark.asyncio
async def test_delete_memory_surfaces_the_service_message() -> None:
    class ConflictingDeleteStore(CrudMemoryStore):
        def delete(self, note_id: str) -> MemoryResponse:
            raise RemoteMemoryStoreError(APPEND_ONLY_409, status_code=409)

    tool = DeleteMemoryTool(memory_store=ConflictingDeleteStore({"mem-1": _note("mem-1", "x")}))

    result = await tool.execute(memory_id="mem-1")

    assert result["success"] is False
    assert "send a follow-up delivery instead" in result["error"]


@pytest.mark.asyncio
async def test_store_memory_surfaces_the_service_message_on_judged_write() -> None:
    class ConflictingRememberStore(RecordingMemoryStore):
        def remember(self, note: MemoryNote, *, force: bool = False) -> MemoryResponse:
            raise RemoteMemoryStoreError(APPEND_ONLY_409, status_code=409)

    tool = StoreMemoryTool(memory_store=ConflictingRememberStore(), task="task")

    result = await tool.execute(content="A durable fact.")

    assert result["success"] is False
    assert "send a follow-up delivery instead" in result["error"]


@pytest.mark.asyncio
async def test_deliver_memory_surfaces_the_service_message() -> None:
    wrapper = _WrappedRemoteStore(RemoteMemoryStore(SERVICE_URL, SERVICE_KEY))
    tool = DeliverMemoryTool(memory_store=wrapper)

    result = await tool.execute(target="t10-probe", content="Ship it.")

    assert result["success"] is False
    assert "send a follow-up delivery instead" in result["error"]


@pytest.mark.asyncio
async def test_search_memory_surfaces_the_service_message() -> None:
    class RateLimitedStore(CrudMemoryStore):
        def search(self, **kwargs: Any) -> list[Any]:
            raise RemoteMemoryStoreError(
                "Remote memory service returned HTTP 429: /v1/memory/search"
                " — rate limited, slow down",
                status_code=429,
            )

    tool = SearchMemoryTool(memory_store=RateLimitedStore())

    result = await tool.execute(query="anything")

    assert result["success"] is False
    assert "rate limited, slow down" in result["error"]


# ---------------------------------------------------------------------------
# search_memory space / category filters (P1-6a, client half)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_memory_forwards_space_and_category_filters() -> None:
    store = CrudMemoryStore()
    tool = SearchMemoryTool(memory_store=store)

    filtered = await tool.execute(
        query="budget", space="department", category="react_memory"
    )
    unfiltered = await tool.execute(query="budget")

    assert filtered["success"] is True
    assert unfiltered["success"] is True
    assert store.searches[0]["filters"] == {
        "space": "department",
        "category": "react_memory",
    }
    # default behaviour is unchanged: no caller filters at all
    assert store.searches[1]["filters"] is None


@pytest.mark.asyncio
async def test_search_memory_rejects_an_unknown_space() -> None:
    store = CrudMemoryStore()
    tool = SearchMemoryTool(memory_store=store)

    result = await tool.execute(query="budget", space="team")

    assert result["success"] is False
    assert "personal" in result["error"] and "department" in result["error"]
    assert store.searches == []


def test_search_memory_schema_advertises_space_and_category() -> None:
    properties = SearchMemoryArgs.model_json_schema()["properties"]
    space_schema = json.dumps(properties["space"])
    for value in ("personal", "department", "company"):
        assert value in space_schema
    assert "category" in properties
