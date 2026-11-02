from types import SimpleNamespace
from typing import Any

import pytest

from xagent.web.api import agents as agents_api


class _FakeLLM:
    def __init__(
        self,
        content: str = "\u8bf7\u51c6\u786e\u7406\u89e3\u7528\u6237\u95ee\u9898，\u6838\u9a8c\u5173\u952e\u4e8b\u5b9e，\u5e76\u7528\u6e05\u6670\u7684\u4e2d\u6587\u4f5c\u7b54。",
    ) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> dict[str, str]:
        self.calls.append(kwargs)
        return {"content": self.content}


class _FakeModelStorage:
    def __init__(self, llm: _FakeLLM) -> None:
        self.llm = llm

    def get_llm_by_id(self, model_id: str, user_id: int) -> _FakeLLM:
        return self.llm

    def get_configured_defaults(self, user_id: int | None = None) -> tuple[Any, ...]:
        return (self.llm, None, None, None)


@pytest.mark.asyncio
async def test_optimize_instructions_preserves_draft_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = _FakeLLM()
    monkeypatch.setattr(
        agents_api,
        "UserAwareModelStorage",
        lambda db: _FakeModelStorage(llm),
    )

    result = await agents_api.optimize_instructions(
        agents_api.OptimizeInstructionsRequest(
            instructions="\u8bf7\u7528\u4e2d\u6587\u56de\u7b54\u7528\u6237\u95ee\u9898。"
        ),
        SimpleNamespace(id=7),
        object(),
    )

    assert result == {
        "optimized_instructions": (
            "\u8bf7\u51c6\u786e\u7406\u89e3\u7528\u6237\u95ee\u9898，\u6838\u9a8c\u5173\u952e\u4e8b\u5b9e，\u5e76\u7528\u6e05\u6670\u7684\u4e2d\u6587\u4f5c\u7b54。"
        )
    }
    system_prompt = llm.calls[0]["messages"][0]["content"]
    assert "draft_instructions" in system_prompt
    assert "explicit or implicit target-language intent" in system_prompt
    assert "Simplified Chinese versus Traditional Chinese" in system_prompt
    assert "surrounding API prompt is written in English only" in system_prompt


@pytest.mark.asyncio
async def test_optimize_instructions_falls_back_on_wrong_language_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = "\u8bf7\u5206\u6790\u7528\u6237\u95ee\u9898，\u6838\u9a8c\u4e8b\u5b9e，\u5e76\u7528\u4e2d\u6587\u7ed9\u51fa\u6e05\u6670\u5b8c\u6574\u7684\u56de\u7b54。"
    llm = _FakeLLM(
        "Analyze the user's request, verify every fact, and return a complete "
        "answer in clear English."
    )
    monkeypatch.setattr(
        agents_api,
        "UserAwareModelStorage",
        lambda db: _FakeModelStorage(llm),
    )

    result = await agents_api.optimize_instructions(
        agents_api.OptimizeInstructionsRequest(instructions=draft),
        SimpleNamespace(id=7),
        object(),
    )

    assert result == {"optimized_instructions": draft}
