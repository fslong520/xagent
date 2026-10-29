"""Task/agent memory-dimension stamping (task/agent memory 断链修复).

Two producers exist for the ``task``/``agent`` memory dimensions:

* the runtime injection in ``web/services/task_execution.py`` -- every task
  execution, fresh or resumed, stamps them onto the resolved scope so notes
  written during the run carry ``execution_scope_task``/``execution_scope_agent``;
* the persisted scope snapshot written at task creation in ``web/api/chat.py``
  -- stored under ``EXECUTION_SCOPE_AGENT_CONFIG_KEY`` so
  ``resolve_execution_scope`` (snapshot loader) reproduces the dimensions
  after a process restart.

Both are pinned here at the helper level; the wire-level stamping itself is
covered by ``tests/core/memory/test_remote.py``.
"""

from __future__ import annotations

from xagent.core.execution_scope import (
    EXECUTION_SCOPE_AGENT_CONFIG_KEY,
    ExecutionScope,
    ExecutionScopeContext,
    execution_scope_from_agent_config,
    get_execution_scope,
    memory_dimension_metadata,
    resolve_execution_scope,
    set_execution_scope_snapshot_loader,
)
from xagent.web.api.chat import _persist_task_memory_dimensions
from xagent.web.models.task import Task
from xagent.web.services.task_execution import _with_task_memory_dimensions


class TestWithTaskMemoryDimensions:
    def test_stamps_task_and_agent(self) -> None:
        scope = _with_task_memory_dimensions(None, 42, 7)

        assert scope.memory_dimensions == {"task": "42", "agent": "7"}

    def test_preserves_existing_scope_fields(self) -> None:
        base = ExecutionScope(
            sandbox_key_suffix="tenant-a",
            workspace_segments=("tenant-a",),
            strict_memory_isolation=True,
        )

        scope = _with_task_memory_dimensions(base, 42, 7)

        assert scope.sandbox_key_suffix == "tenant-a"
        assert scope.workspace_segments == ("tenant-a",)
        assert scope.strict_memory_isolation is True
        assert scope.memory_dimensions == {"task": "42", "agent": "7"}

    def test_existing_dimension_values_win(self) -> None:
        """A resolver/snapshot that named its own task/agent value is authoritative."""
        base = ExecutionScope(
            memory_dimensions={"task": "resolver-says", "tenant": "a"}
        )

        scope = _with_task_memory_dimensions(base, 42, 7)

        assert scope.memory_dimensions == {
            "task": "resolver-says",
            "agent": "7",
            "tenant": "a",
        }

    def test_agent_omitted_when_task_has_none(self) -> None:
        scope = _with_task_memory_dimensions(None, 42, None)

        assert scope.memory_dimensions == {"task": "42"}

    def test_stamped_metadata_carries_the_prefix(self) -> None:
        scope = _with_task_memory_dimensions(None, 42, 7)

        assert memory_dimension_metadata(scope) == {
            "execution_scope_task": "42",
            "execution_scope_agent": "7",
        }


class TestPersistTaskMemoryDimensions:
    def test_persists_snapshot_with_task_and_agent(self) -> None:
        task = Task(id=42, agent_id=7)

        _persist_task_memory_dimensions(task)

        decoded = execution_scope_from_agent_config(task.agent_config)
        assert decoded is not None
        assert decoded.memory_dimensions == {"task": "42", "agent": "7"}

    def test_agent_omitted_when_task_has_none(self) -> None:
        task = Task(id=42, agent_id=None)

        _persist_task_memory_dimensions(task)

        decoded = execution_scope_from_agent_config(task.agent_config)
        assert decoded is not None
        assert decoded.memory_dimensions == {"task": "42"}

    def test_merges_with_existing_snapshot(self) -> None:
        existing = ExecutionScope(
            sandbox_key_suffix="tenant-a",
            workspace_segments=("tenant-a",),
            memory_dimensions={"tenant": "a"},
        )
        task = Task(
            id=42,
            agent_id=7,
            agent_config={EXECUTION_SCOPE_AGENT_CONFIG_KEY: existing.to_dict()},
        )

        _persist_task_memory_dimensions(task)

        decoded = execution_scope_from_agent_config(task.agent_config)
        assert decoded is not None
        assert decoded.sandbox_key_suffix == "tenant-a"
        assert decoded.workspace_segments == ("tenant-a",)
        assert decoded.memory_dimensions == {
            "tenant": "a",
            "task": "42",
            "agent": "7",
        }

    def test_existing_task_dimension_wins(self) -> None:
        existing = ExecutionScope(memory_dimensions={"task": "snapshot-says"})
        task = Task(
            id=42,
            agent_id=7,
            agent_config={EXECUTION_SCOPE_AGENT_CONFIG_KEY: existing.to_dict()},
        )

        _persist_task_memory_dimensions(task)

        decoded = execution_scope_from_agent_config(task.agent_config)
        assert decoded is not None
        assert decoded.memory_dimensions == {
            "task": "snapshot-says",
            "agent": "7",
        }

    def test_unrelated_config_keys_survive(self) -> None:
        task = Task(id=42, agent_id=7, agent_config={"foo": "bar"})

        _persist_task_memory_dimensions(task)

        assert task.agent_config["foo"] == "bar"


class TestCreationToStampChain:
    """In-process chain: create → persisted snapshot → restart resolution →
    runtime injection → the metadata stamps add/remember write to the wire."""

    def test_survives_restart_and_stamps(self) -> None:
        # Creation path persists the snapshot into agent_config.
        task = Task(id=42, agent_id=7)
        _persist_task_memory_dimensions(task)
        # A restarted process only sees the persisted row.
        row_agent_config = dict(task.agent_config)

        def loader(task_id: object) -> ExecutionScope | None:
            if str(task_id) != "42":
                return None
            return execution_scope_from_agent_config(row_agent_config)

        set_execution_scope_snapshot_loader(loader)
        try:
            # No resolver registered: the snapshot is the sole answer.
            resolved = resolve_execution_scope(42)
            assert resolved is not None
            assert resolved.memory_dimensions == {"task": "42", "agent": "7"}

            # Runtime injection keeps the values (no clobbering) and the
            # active scope's stamps are exactly what add/remember write.
            runtime = _with_task_memory_dimensions(resolved, 42, None)
            with ExecutionScopeContext(runtime):
                assert memory_dimension_metadata(get_execution_scope()) == {
                    "execution_scope_task": "42",
                    "execution_scope_agent": "7",
                }
        finally:
            set_execution_scope_snapshot_loader(None)
