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
        content="\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA9999，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。",
        tags=["\u8f66\u724c\u53f7", "\u4eacA8888"],
        keywords=["\u8f66\u724c\u53f7", "\u4eacA8888"],
    )

    removed = drop_replaced_tags(note, "\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。")

    assert removed == ["\u4eacA8888"]
    assert note.tags == ["\u8f66\u724c\u53f7"]
    assert note.keywords == ["\u8f66\u724c\u53f7"]


def test_cleans_keywords_when_the_tag_list_is_already_empty() -> None:
    """The old early return left ``keywords`` to refill the empty tags."""
    note = MemoryNote(
        content="\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA9999，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。",
        tags=[],
        keywords=["\u8f66\u724c\u53f7", "\u4eacA8888"],
    )

    removed = drop_replaced_tags(note, "\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。")

    assert removed == []
    assert note.tags == []
    assert note.keywords == ["\u8f66\u724c\u53f7"]


def test_keeps_classification_markers_that_never_appeared_in_the_body() -> None:
    note = MemoryNote(
        content="\u65b0\u7684\u6b63\u6587，\u4e0d\u518d\u63d0\u5230\u8f66\u724c。",
        tags=["\u505c\u8f66\u4fe1\u606f", "\u9ad8\u9891"],
        keywords=["\u505c\u8f66\u7c7b", "\u957f\u6587\u672c"],
    )

    drop_replaced_tags(note, "\u65e7\u6b63\u6587，\u542b \u4eacA8888。")

    assert note.tags == ["\u505c\u8f66\u4fe1\u606f", "\u9ad8\u9891"]
    assert note.keywords == ["\u505c\u8f66\u7c7b", "\u957f\u6587\u672c"]


def test_keeps_a_value_the_new_body_still_supports() -> None:
    note = MemoryNote(
        content="\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA9999，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。",
        tags=["\u8f66\u724c\u53f7"],
        keywords=["\u8f66\u724c\u53f7"],
    )

    drop_replaced_tags(note, "\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888，\u505c\u8f66\u6708\u5361\u767b\u8bb0\u7528。")

    assert note.tags == ["\u8f66\u724c\u53f7"]
    assert note.keywords == ["\u8f66\u724c\u53f7"]


def test_unchanged_body_leaves_tags_and_keywords_alone() -> None:
    note = MemoryNote(
        content="\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888。",
        tags=["\u4eacA8888"],
        keywords=["\u4eacA8888"],
    )

    removed = drop_replaced_tags(note, "\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888。")

    assert removed == []
    assert note.tags == ["\u4eacA8888"]
    assert note.keywords == ["\u4eacA8888"]


def test_compares_bodies_after_collapsing_whitespace() -> None:
    """A rewrite that only changes line breaks replaced nothing."""
    note = MemoryNote(
        content="\u6211\u7684\u8f66\u724c\u53f7\u662f\n\u4eacA8888。",
        tags=["\u4eacA8888"],
        keywords=["\u4eacA8888"],
    )

    drop_replaced_tags(note, "\u6211\u7684\u8f66\u724c\u53f7\u662f \u4eacA8888。")

    assert note.tags == ["\u4eacA8888"]
    assert note.keywords == ["\u4eacA8888"]
