"""Tests for ReAct-based creation of a Workforce and its agents."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from xagent.core.agent.budget import ExecutionBudgetPolicy
from xagent.core.model.chat.token_context import add_token_usage
from xagent.web.services import workforce_creator, workforce_prompt_runtime
from xagent.web.services.workforce_creator import (
    generate_workforce_creation_plan,
    get_localized_description,
)
from xagent.web.services.workforce_prompt_runtime import (
    MAX_WORKFORCE_BUILDER_AGENTS,
    MAX_WORKFORCE_BUILDER_EXISTING_AGENTS,
    ListAvailableAgentsTool,
    WorkforcePromptBuilderError,
    WorkforcePromptBuilderState,
    WorkforcePromptBuilderUnavailableError,
    _validate_builder_plan_language,
    build_workforce_prompt_plan,
    workforce_prompt_builder_system_prompt,
)


class FakeLLM:
    model_name = "fake-workforce-builder"

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_calls": [
            {
                "id": call_id,
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        ]
    }


def _stage_agent(
    state: WorkforcePromptBuilderState,
    *,
    name: str,
    instructions: str,
    mode: str = "balanced",
) -> str:
    result = state.stage_agent(
        {
            "name": name,
            "description": f"When to use {name}",
            "instructions": instructions,
            "execution_mode": mode,
        }
    )
    assert result["status"] == "success"
    return str(result["agent_ref"])


def test_builder_prompt_requires_multi_agent_react_and_language_harness() -> None:
    prompt = workforce_prompt_builder_system_prompt()
    normalized_prompt = " ".join(prompt.split())

    assert "not a one-shot JSON planning task" in normalized_prompt
    assert "call create_agent separately" in normalized_prompt
    assert "every create_agent call succeeded" in normalized_prompt
    assert "one transaction" in normalized_prompt
    assert "Simplified Chinese" in prompt
    assert "Traditional Chinese" in prompt
    assert "DAG step" not in prompt
    assert "dependencies" not in prompt


def test_builder_state_requires_all_agents_before_finalization() -> None:
    state = WorkforcePromptBuilderState.from_agents([])
    manager_ref = _stage_agent(
        state,
        name="Research Manager",
        instructions="Break down the task, delegate and synthesise the results.",
        mode="think",
    )
    worker_ref = _stage_agent(
        state,
        name="Researcher",
        instructions="Retrieve and verify sources.",
    )

    before_listing = state.finalize(
        {
            "name": "Research Workforce",
            "description": "Deliver research tasks.",
            "manager_agent_ref": manager_ref,
            "workers": [
                {
                    "agent_ref": worker_ref,
                    "assignment_instructions": "Collect and verify sources.",
                }
            ],
        }
    )
    assert before_listing["status"] == "error"

    state.listed_existing_agents = True
    finalized = state.finalize(
        {
            "name": "Research Workforce",
            "description": "Deliver research tasks.",
            "manager_agent_ref": manager_ref,
            "workers": [
                {
                    "agent_ref": worker_ref,
                    "assignment_instructions": "Collect and verify sources.",
                }
            ],
        }
    )

    assert finalized["status"] == "success"
    plan = state.to_plan()
    assert len(plan["created_agents"]) == 2
    assert all(agent["tool_categories"] == [] for agent in plan["created_agents"])
    assert plan["manager"]["agent_ref"] == manager_ref
    assert plan["workers"][0]["agent_ref"] == worker_ref


def test_builder_state_rejects_unused_or_failed_staged_agents() -> None:
    state = WorkforcePromptBuilderState.from_agents([])
    failed = state.stage_agent(
        {"name": "Invalid Agent", "description": "Description", "instructions": ""}
    )
    assert failed["status"] == "error"
    assert state.created_agents == {}

    manager_ref = _stage_agent(
        state,
        name="Manager",
        instructions="Coordinate the work.",
        mode="think",
    )
    used_worker_ref = _stage_agent(
        state,
        name="Researcher",
        instructions="Carry out research.",
    )
    _stage_agent(state, name="Unused Agent", instructions="Do other work.")
    state.listed_existing_agents = True

    result = state.finalize(
        {
            "name": "Workforce",
            "description": "Execute the task.",
            "manager_agent_ref": manager_ref,
            "workers": [
                {
                    "agent_ref": used_worker_ref,
                    "assignment_instructions": "Carry out research.",
                }
            ],
        }
    )

    assert result["status"] == "error"
    assert "Unused refs" in result["message"]
    with pytest.raises(WorkforcePromptBuilderError):
        state.to_plan()


def test_builder_state_validates_tool_categories_like_create_agent() -> None:
    state = WorkforcePromptBuilderState.from_agents([])
    for categories, expected in (
        (["web_search", "email"], "['email'] are not assignable"),
        (
            ["web_search", "mcp:github"],
            "cannot grant; once it is created, the user can add connectors to its worker agents",
        ),
        (["mcp"], "built from a prompt cannot grant"),
        ({"a": 1}, "must be a list"),
        (False, "must be a list"),
    ):
        result = state.stage_agent(
            {
                "name": "Researcher",
                "description": "Used when retrieving sources.",
                "instructions": "Retrieve and verify sources.",
                "tool_categories": categories,
            }
        )
        assert result["status"] == "error", categories
        assert expected in result["message"], categories
    assert state.created_agents == {}

    staged = state.stage_agent(
        {
            "name": "Researcher",
            "description": "Used when retrieving sources.",
            "instructions": "Retrieve and verify sources.",
            "tool_categories": [" web_search", "web_search"],
        }
    )
    assert staged["status"] == "success"
    assert state.created_agents[staged["agent_ref"]].tool_categories == ["web_search"]


def test_builder_state_enforces_staged_agent_limit() -> None:
    state = WorkforcePromptBuilderState.from_agents([])
    for index in range(MAX_WORKFORCE_BUILDER_AGENTS):
        result = state.stage_agent(
            {
                "name": f"Agent {index}",
                "description": "Performs one bounded role.",
                "instructions": "Complete the assigned bounded role.",
            }
        )
        assert result["status"] == "success"

    rejected = state.stage_agent(
        {
            "name": "One agent too many",
            "description": "Must be rejected.",
            "instructions": "Do not stage this agent.",
        }
    )

    assert rejected["status"] == "error"
    assert "staged-agent limit" in rejected["message"]


def test_builder_language_validation_rejects_wrong_script_before_persistence() -> None:
    with pytest.raises(WorkforcePromptBuilderError, match="workforce.name"):
        _validate_builder_plan_language(
            # The request is in Chinese, so an all-English plan must be rejected.
            prompt="\u521b\u5efa\u4e00\u4e2a\u7528\u4e8e\u5206\u6790\u5e02\u573a\u6570\u636e\u7684\u5de5\u4f5c\u7ec4\u3002",
            plan={
                "name": "Market Research Workforce",
                "description": (
                    "Research the market, compare all evidence, and produce a "
                    "complete English report for the user."
                ),
                "created_agents": [],
                "workers": [],
                "builder_response": "The requested Workforce is ready.",
            },
        )


def test_builder_language_validation_allows_explicit_target_language() -> None:
    _validate_builder_plan_language(
        prompt=(
            "Create a research Workforce, but write every persisted field and "
            "the final response in Chinese."
        ),
        plan={
            "name": "Market Research Workforce",
            "description": "Research market data and summarise the key findings.",
            "created_agents": [
                {
                    "name": "Market Researcher",
                    "description": "Collect and verify market evidence.",
                    "instructions": "Retrieve reliable sources and summarise them in Chinese.",
                }
            ],
            "workers": [
                {
                    "alias": "Market Research",
                    "assignment_instructions": "Collect and verify market evidence.",
                }
            ],
            "builder_response": "The Workforce has been configured.",
        },
    )


@pytest.mark.asyncio
async def test_react_builder_creates_multiple_agents_before_workforce() -> None:
    llm = FakeLLM(
        [
            _tool_call("list", "list_available_agents", {}),
            _tool_call(
                "manager",
                "create_agent",
                {
                    "name": "Product Research Manager",
                    "description": "Coordinate product research work.",
                    "instructions": "Break down goals, delegate tasks, compare evidence and synthesise conclusions.",
                    "execution_mode": "think",
                },
            ),
            _tool_call(
                "researcher",
                "create_agent",
                {
                    "name": "Market Researcher",
                    "description": "Used to collect and verify market material.",
                    "instructions": "Retrieve reliable sources, cross-check them and record citations.",
                    "tool_categories": ["web_search"],
                },
            ),
            _tool_call(
                "analyst",
                "create_agent",
                {
                    "name": "Product Analyst",
                    "description": "Used to compare product capabilities and differences.",
                    "instructions": "Define comparison dimensions, analyse differences and flag risks.",
                },
            ),
            _tool_call(
                "workforce",
                "create_workforce",
                {
                    "name": "Product Research Workforce",
                    "description": "Research the market and produce product analysis conclusions.",
                    "manager_agent_ref": "new:1",
                    "workers": [
                        {
                            "agent_ref": "new:2",
                            "alias": "Market Research",
                            "assignment_instructions": "Collect and verify market evidence.",
                        },
                        {
                            "agent_ref": "new:3",
                            "alias": "Product Analysis",
                            "assignment_instructions": "Compare the products and summarise the differences.",
                        },
                    ],
                },
            ),
            _tool_call(
                "final",
                "final_answer",
                {
                    "response_language": "Simplified Chinese",
                    "answer": "The Workforce has been configured.",
                    "outcome": "completed",
                },
            ),
        ]
    )

    plan = await build_workforce_prompt_plan(
        prompt="Create a product research Workforce that needs market research and product analysis.",
        llm=llm,
        available_agents=[],
    )

    assert [agent["agent_ref"] for agent in plan["created_agents"]] == [
        "new:1",
        "new:2",
        "new:3",
    ]
    assert [worker["agent_ref"] for worker in plan["workers"]] == [
        "new:2",
        "new:3",
    ]
    assert plan["name"] == "Product Research Workforce"
    assert plan["builder_response"] == "The Workforce has been configured."
    assert len(llm.calls) == 6
    first_tool_names = {schema["function"]["name"] for schema in llm.calls[0]["tools"]}
    assert first_tool_names == {
        "ask_user_question",
        "create_agent",
        "create_workforce",
        "final_answer",
        "list_available_agents",
        "list_available_skills",
        "list_tool_categories",
        "send_message",
    }


def _recording_agent_service_class(captured_kwargs: dict[str, Any]) -> type:
    """A fake AgentService that records its constructor kwargs and reports
    a bare completion with no finalized Workforce - used by the two voice
    tests below, which only need the constructor call to have happened."""

    class RecordingAgentService:
        def __init__(self, **kwargs: Any) -> None:
            captured_kwargs.update(kwargs)

        def set_allowed_skills(self, _allowed_skills: list[str]) -> None:
            pass

        async def execute_task(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"success": True, "completion_outcome": "completed"}

    return RecordingAgentService


@pytest.mark.asyncio
async def test_build_workforce_prompt_plan_applies_voice_to_system_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """builder_response is a free-text assistant reply persisted into the
    Workforce's conversation - the same "every agent this user talks to"
    voice policy that Builder chat and task chat already apply must reach
    this runtime's own AgentService too."""
    captured_kwargs: dict[str, Any] = {}
    monkeypatch.setattr(
        workforce_prompt_runtime,
        "AgentService",
        _recording_agent_service_class(captured_kwargs),
    )
    monkeypatch.setattr(
        workforce_prompt_runtime,
        "extract_assistant_message",
        lambda _result: "The Workforce has been configured.",
    )

    with pytest.raises(WorkforcePromptBuilderError):
        # The mock never calls create_workforce, so to_plan() raises - the
        # assertion below only needs the AgentService construction to have
        # already happened, which it has by this point.
        await build_workforce_prompt_plan(
            prompt="Create a product research Workforce.",
            llm=FakeLLM([]),
            available_agents=[],
            voice="warm",
        )

    system_prompt = captured_kwargs["system_prompt"]
    assert system_prompt.startswith(
        workforce_prompt_builder_system_prompt() + "\n\n## OUTPUT VOICE\n"
    )
    assert "Empathetic and reassuring" in system_prompt
    # apply_output_voice's own scoping caveat (not something this call
    # site adds itself) must still cover create_agent/create_workforce's
    # persisted arguments here, or a tone like "concise" could start
    # trimming agent names/descriptions/instructions too.
    assert "persisted as configuration" in system_prompt
    assert system_prompt.index("## OUTPUT VOICE") < system_prompt.index(
        "persisted as configuration"
    )


@pytest.mark.asyncio
async def test_build_workforce_prompt_plan_without_voice_leaves_prompt_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}
    monkeypatch.setattr(
        workforce_prompt_runtime,
        "AgentService",
        _recording_agent_service_class(captured_kwargs),
    )

    def budget_provider():
        return ExecutionBudgetPolicy(max_tokens=123)

    with pytest.raises(WorkforcePromptBuilderError):
        await build_workforce_prompt_plan(
            prompt="Create a product research Workforce.",
            llm=FakeLLM([]),
            available_agents=[],
            budget_policy_provider=budget_provider,
        )

    assert captured_kwargs["system_prompt"] == workforce_prompt_builder_system_prompt()
    assert captured_kwargs["budget_policy_provider"] is budget_provider


@pytest.mark.asyncio
async def test_available_agent_tool_bounds_each_model_result() -> None:
    state = WorkforcePromptBuilderState.from_agents(
        [
            {
                "agent_id": index,
                "name": f"Research Agent {index}",
                "description": "Collects and verifies evidence.",
                "status": "published",
            }
            for index in range(1, 31)
        ]
    )

    result = await ListAvailableAgentsTool(state).run_json_async(
        {"query": "research", "limit": 7}
    )

    assert len(result["agents"]) == 7
    assert result["total_matches"] == 30
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_react_builder_does_not_report_success_without_finalization() -> None:
    llm = FakeLLM(
        [
            _tool_call(
                "final",
                "final_answer",
                {
                    "response_language": "English",
                    "answer": "Done.",
                    "outcome": "completed",
                },
            )
        ]
    )

    with pytest.raises(
        WorkforcePromptBuilderError,
        match="did not call create_workforce successfully",
    ):
        await build_workforce_prompt_plan(
            prompt="Create a research Workforce.",
            llm=llm,
            available_agents=[],
        )


@pytest.mark.asyncio
async def test_react_builder_wraps_execution_boundary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailableAgentService:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def set_allowed_skills(self, _allowed_skills: list[str]) -> None:
            pass

        async def execute_task(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("registry initialization failed")

    monkeypatch.setattr(
        workforce_prompt_runtime,
        "AgentService",
        UnavailableAgentService,
    )

    with pytest.raises(
        WorkforcePromptBuilderUnavailableError,
        match="runtime is unavailable",
    ):
        await build_workforce_prompt_plan(
            prompt="Create a research Workforce.",
            llm=FakeLLM([]),
            available_agents=[],
        )


@pytest.mark.asyncio
async def test_generation_fails_clearly_when_no_model_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoModelStorage:
        def __init__(self, _db: object) -> None:
            pass

        def get_configured_defaults(
            self, _user_id: int | None
        ) -> tuple[None, None, None, None]:
            return None, None, None, None

    monkeypatch.setattr(workforce_creator, "UserAwareModelStorage", NoModelStorage)
    monkeypatch.setattr(
        workforce_creator,
        "list_accessible_published_agents",
        lambda _db, _user, **_kwargs: [],
    )

    with pytest.raises(HTTPException) as exc_info:
        await generate_workforce_creation_plan(
            object(),
            type("User", (), {"id": 7})(),
            "Create a research Workforce",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "workforce_prompt_builder_unavailable"


@pytest.mark.asyncio
async def test_generation_releases_database_before_react_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM([])
    events: list[str] = []
    catalog_limits: list[int | None] = []
    resolve_budget = AsyncMock(return_value=ExecutionBudgetPolicy(max_tokens=123))
    monkeypatch.setattr(
        "xagent.web.services.execution_budget.resolve_execution_budget_policy",
        resolve_budget,
    )

    class ModelStorage:
        def __init__(self, _db: object) -> None:
            pass

        def get_configured_defaults(self, _user_id: int | None) -> tuple[Any, ...]:
            return (llm, None, None, None)

    async def fake_build_workforce_prompt_plan(**kwargs: Any) -> dict[str, Any]:
        events.append("runtime")
        assert (await kwargs["budget_policy_provider"]()).max_tokens == 123
        request = resolve_budget.await_args.args[0]
        assert (request.user_id, request.task_id, request.scope) == (7, None, None)
        assert kwargs["available_agents"] == [
            {
                "agent_id": 12,
                "name": "Researcher",
                "description": "Collects evidence.",
                "status": "published",
            }
        ]
        return {"name": "Research Workforce"}

    monkeypatch.setattr(workforce_creator, "UserAwareModelStorage", ModelStorage)

    def list_agents(
        _db: object,
        _user: object,
        *,
        limit: int | None = None,
    ) -> list[SimpleNamespace]:
        catalog_limits.append(limit)
        return [
            SimpleNamespace(
                id=12,
                name="Researcher",
                description="Collects evidence.",
                status=SimpleNamespace(value="published"),
            )
        ]

    monkeypatch.setattr(
        workforce_creator,
        "list_accessible_published_agents",
        list_agents,
    )
    monkeypatch.setattr(
        workforce_creator,
        "release_db_connection_if_clean",
        lambda _db: events.append("release") or True,
    )
    monkeypatch.setattr(
        workforce_creator,
        "build_workforce_prompt_plan",
        fake_build_workforce_prompt_plan,
    )

    result = await generate_workforce_creation_plan(
        object(),
        SimpleNamespace(id=7),
        "Create a research Workforce.",
    )

    assert result == {"name": "Research Workforce"}
    assert events == ["release", "runtime"]
    assert catalog_limits == [MAX_WORKFORCE_BUILDER_EXISTING_AGENTS]


@pytest.mark.asyncio
async def test_workforce_budget_stop_names_the_setting_instead_of_generic_incomplete():
    class MeteredBuilderLLM(FakeLLM):
        async def chat(self, **kwargs):
            response = await super().chat(**kwargs)
            add_token_usage(input_tokens=9, output_tokens=1)
            return response

    llm = MeteredBuilderLLM([_tool_call("list", "list_available_agents", {})])
    with pytest.raises(
        WorkforcePromptBuilderError, match="execution token budget"
    ) as exc:
        await build_workforce_prompt_plan(
            prompt="Create a research Workforce.",
            llm=llm,
            available_agents=[],
            budget_policy_provider=lambda: ExecutionBudgetPolicy(max_tokens=1),
        )
    assert "Settings > Execution budget" in str(exc.value)
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_generation_resolves_voice_from_the_user_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generate_workforce_creation_plan must resolve voice from the live
    `user` row and thread it into build_workforce_prompt_plan - the two
    build_workforce_prompt_plan tests above only exercise that function
    directly with an explicit voice= kwarg, not this caller's own
    resolution step, which is what's under test here."""
    llm = FakeLLM([])
    captured_voice: list[str | None] = []

    class ModelStorage:
        def __init__(self, _db: object) -> None:
            pass

        def get_configured_defaults(self, _user_id: int | None) -> tuple[Any, ...]:
            return (llm, None, None, None)

    async def fake_build_workforce_prompt_plan(**kwargs: Any) -> dict[str, Any]:
        captured_voice.append(kwargs["voice"])
        return {"name": "Research Workforce"}

    monkeypatch.setattr(workforce_creator, "UserAwareModelStorage", ModelStorage)
    monkeypatch.setattr(
        workforce_creator,
        "list_accessible_published_agents",
        lambda _db, _user, **_kwargs: [],
    )
    monkeypatch.setattr(
        workforce_creator, "release_db_connection_if_clean", lambda _db: True
    )
    monkeypatch.setattr(
        workforce_creator,
        "build_workforce_prompt_plan",
        fake_build_workforce_prompt_plan,
    )

    await generate_workforce_creation_plan(
        object(),
        SimpleNamespace(id=7, preferences={"voice": "warm"}),
        "Create a research Workforce.",
    )

    assert captured_voice == ["warm"]


@pytest.mark.asyncio
async def test_generation_maps_runtime_boundary_failure_to_stable_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM([])

    class ModelStorage:
        def __init__(self, _db: object) -> None:
            pass

        def get_configured_defaults(self, _user_id: int | None) -> tuple[Any, ...]:
            return (llm, None, None, None)

    async def unavailable_builder(**_kwargs: Any) -> dict[str, Any]:
        raise WorkforcePromptBuilderUnavailableError("adapter setup failed")

    monkeypatch.setattr(workforce_creator, "UserAwareModelStorage", ModelStorage)
    monkeypatch.setattr(
        workforce_creator,
        "list_accessible_published_agents",
        lambda _db, _user, **_kwargs: [],
    )
    monkeypatch.setattr(
        workforce_creator,
        "release_db_connection_if_clean",
        lambda _db: True,
    )
    monkeypatch.setattr(
        workforce_creator,
        "build_workforce_prompt_plan",
        unavailable_builder,
    )

    with pytest.raises(HTTPException) as exc_info:
        await generate_workforce_creation_plan(
            object(),
            SimpleNamespace(id=7),
            "Create a research Workforce.",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "workforce_prompt_builder_unavailable"


def test_get_localized_description_prefers_english() -> None:
    template = {
        "descriptions": {"en": "English description", "zh": "Chinese description"}
    }

    assert get_localized_description(template) == "English description"


def test_get_localized_description_falls_back_to_another_locale() -> None:
    """`_parse_yaml_file` only requires an 'en' *key* to be present, not a
    non-empty value, so a template can carry an empty English description
    alongside a populated one in another locale - the Workforce's
    description shouldn't end up empty just because English is blank."""
    template = {"descriptions": {"en": "", "zh": "Chinese description"}}

    assert get_localized_description(template) == "Chinese description"


def test_get_localized_description_returns_none_when_nothing_is_populated() -> None:
    assert get_localized_description({"descriptions": {"en": "", "zh": ""}}) is None
    assert get_localized_description({"descriptions": "not a dict"}) is None
    assert get_localized_description({}) is None
