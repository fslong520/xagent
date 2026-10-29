"""X-06: dropping tags/keywords that only the replaced text supported.

The service keeps whichever tags a PUT carries and refills an empty tag list
from ``keywords`` (probed 2026-10-29, ``.probe-x06-tags-20261029/``), so the
client owns the cleanup. These tests pin the two behaviours the rework added:
keywords are cleaned even when ``tags`` is already empty, and a value that
never appeared in the body (a classification marker) is never touched.
"""

from xagent.core.memory.core import MemoryNote, drop_replaced_tags


def test_drops_the_tag_the_new_body_replaced() -> None:
    note = MemoryNote(
        content="我的车牌号是 京A9999，停车月卡登记用。",
        tags=["车牌号", "京A8888"],
        keywords=["车牌号", "京A8888"],
    )

    removed = drop_replaced_tags(note, "我的车牌号是 京A8888，停车月卡登记用。")

    assert removed == ["京A8888"]
    assert note.tags == ["车牌号"]
    assert note.keywords == ["车牌号"]


def test_cleans_keywords_when_the_tag_list_is_already_empty() -> None:
    """The old early return left ``keywords`` to refill the empty tags."""
    note = MemoryNote(
        content="我的车牌号是 京A9999，停车月卡登记用。",
        tags=[],
        keywords=["车牌号", "京A8888"],
    )

    removed = drop_replaced_tags(note, "我的车牌号是 京A8888，停车月卡登记用。")

    assert removed == []
    assert note.tags == []
    assert note.keywords == ["车牌号"]


def test_keeps_classification_markers_that_never_appeared_in_the_body() -> None:
    note = MemoryNote(
        content="新的正文，不再提到车牌。",
        tags=["停车信息", "高频"],
        keywords=["停车类", "长文本"],
    )

    drop_replaced_tags(note, "旧正文，含 京A8888。")

    assert note.tags == ["停车信息", "高频"]
    assert note.keywords == ["停车类", "长文本"]


def test_keeps_a_value_the_new_body_still_supports() -> None:
    note = MemoryNote(
        content="我的车牌号是 京A9999，停车月卡登记用。",
        tags=["车牌号"],
        keywords=["车牌号"],
    )

    drop_replaced_tags(note, "我的车牌号是 京A8888，停车月卡登记用。")

    assert note.tags == ["车牌号"]
    assert note.keywords == ["车牌号"]


def test_unchanged_body_leaves_tags_and_keywords_alone() -> None:
    note = MemoryNote(
        content="我的车牌号是 京A8888。",
        tags=["京A8888"],
        keywords=["京A8888"],
    )

    removed = drop_replaced_tags(note, "我的车牌号是 京A8888。")

    assert removed == []
    assert note.tags == ["京A8888"]
    assert note.keywords == ["京A8888"]


def test_compares_bodies_after_collapsing_whitespace() -> None:
    """A rewrite that only changes line breaks replaced nothing."""
    note = MemoryNote(
        content="我的车牌号是\n京A8888。",
        tags=["京A8888"],
        keywords=["京A8888"],
    )

    drop_replaced_tags(note, "我的车牌号是 京A8888。")

    assert note.tags == ["京A8888"]
    assert note.keywords == ["京A8888"]
