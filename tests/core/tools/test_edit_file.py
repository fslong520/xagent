"""
Tests for the edit_file tool.
"""

import os
import tempfile

import pytest

from xagent.core.tools.core.file_tool import (
    EditOperation,
    _delete_lines,
    _insert_lines,
    _replace_lines,
    edit_file,
    find_and_replace,
)


class TestEditFile:
    """Tests for the edit_file tool."""

    def setup_method(self):
        """Set up before each test method."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self.test_content = """Line 1
Line 2
Line 3
Line 4
Line 5"""
        self.temp_file.write(self.test_content)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up after each test method."""
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_edit_file_replace_by_line_number(self):
        """Test replace operation by line number."""
        operations = [
            {
                "operation_type": "replace",
                "line_number": 3,
                "content": "Modified Line Three",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1
        assert "Modified Line Three" in result.preview

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Modified Line Three" in content
        assert "Line 3\n" not in content  # The original Line 3 should be fully replaced
        assert content == "Line 1\nLine 2\nModified Line Three\nLine 4\nLine 5"

    def test_edit_file_replace_by_pattern(self):
        """Test replace operation by pattern match."""
        operations = [
            {
                "operation_type": "replace",
                "pattern": r"Line 2",
                "content": "Replaced Line Two",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Replaced Line Two" in content
        assert "Line 2\n" not in content  # The original Line 2 should be fully replaced
        assert content == "Line 1\nReplaced Line Two\nLine 3\nLine 4\nLine 5"

    def test_edit_file_insert_by_line_number(self):
        """Test insert operation by line number."""
        operations = [
            {"operation_type": "insert", "line_number": 3, "content": "Inserted Line"}
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            lines = f.readlines()

        assert len(lines) == 6  # Originally 5 lines, one line inserted
        assert "Inserted Line\n" in lines[2]  # Inserted at the third line position

    def test_edit_file_insert_by_pattern(self):
        """Test insert operation by pattern match."""
        operations = [
            {
                "operation_type": "insert",
                "pattern": r"Line 3",
                "content": "Inserted after Line 3",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            lines = f.readlines()

        assert len(lines) == 6
        assert "Inserted after Line 3\n" in lines[3]  # Inserted after Line 3

    def test_edit_file_delete_by_line_number(self):
        """Test delete operation by line number."""
        operations = [{"operation_type": "delete", "line_number": 3}]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            lines = f.readlines()

        assert len(lines) == 4  # Originally 5 lines, one line deleted
        assert "Line 3\n" not in lines

    def test_edit_file_delete_by_pattern(self):
        """Test delete operation by pattern match."""
        operations = [{"operation_type": "delete", "pattern": r"Line 2"}]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Line 2" not in content

    def test_edit_file_multiple_operations(self):
        """Test multiple operations."""
        operations = [
            {
                "operation_type": "replace",
                "line_number": 2,
                "content": "Modified Line 2",
            },
            {"operation_type": "insert", "line_number": 4, "content": "Inserted Line"},
            {
                "operation_type": "replace",
                "pattern": r"Line 5",
                "content": "Final Line",
            },
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 3

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Modified Line 2" in content
        assert "Inserted Line" in content
        assert "Final Line" in content

    def test_edit_file_with_backup(self):
        """Test backup file creation."""
        operations = [
            {
                "operation_type": "replace",
                "line_number": 1,
                "content": "Modified first line",
            }
        ]

        result = edit_file(self.temp_file.name, operations, backup=True)

        assert result.success is True

        # Check whether the backup file was created
        backup_file = self.temp_file.name + ".backup"
        assert os.path.exists(backup_file)

        with open(backup_file, "r") as f:
            backup_content = f.read()

        assert backup_content == self.test_content

        with open(self.temp_file.name, "r") as f:
            current_content = f.read()

        assert current_content != backup_content

    def test_edit_file_with_edit_operation_objects(self):
        """Test using EditOperation objects."""
        operations = [
            EditOperation(
                operation_type="replace",
                line_number=2,
                content="Using EditOperation object",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert "Using EditOperation object" in result.preview

    def test_edit_file_file_not_found(self):
        """Test the case where the file does not exist."""
        with pytest.raises(FileNotFoundError):
            edit_file("/nonexistent/file.txt", [])

    def test_edit_file_invalid_line_number(self):
        """Test invalid line number."""
        operations = [
            {"operation_type": "replace", "line_number": 999, "content": "Content"}
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is False
        assert "out of range" in result.message

    def test_edit_file_no_matching_pattern(self):
        """Test no matching pattern."""
        operations = [
            {
                "operation_type": "replace",
                "pattern": r"NonExistentPattern",
                "content": "Content",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is False
        assert "No lines found matching pattern" in result.message

    def test_edit_file_field_mapping_alternative_names(self):
        """Test operation mapping with alternative field names (type->operation_type, target->pattern, replacement->content)."""
        operations = [
            {
                "type": "replace",
                "target": r"Line 2",
                "replacement": "Replaced using alternative field names",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Replaced using alternative field names" in content
        assert "Line 2\n" not in content
        assert (
            content
            == "Line 1\nReplaced using alternative field names\nLine 3\nLine 4\nLine 5"
        )

    def test_edit_file_field_mapping_mixed_names(self):
        """Test mixing standard and alternative field names."""
        operations = [
            {
                "type": "replace",  # Alternative field name
                "line_number": 2,
                "content": "Mixed field names 1",
            },
            {
                "operation_type": "replace",  # Standard field name
                "pattern": r"Line 4",
                "content": "Mixed field names 2",
            },
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 2

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Mixed field names 1" in content
        assert "Mixed field names 2" in content
        assert "Line 2\n" not in content
        assert "Line 4\n" not in content

    def test_edit_file_field_mapping_insert_with_alternative_names(self):
        """Test insert operation using alternative field names."""
        operations = [
            {
                "type": "insert",
                "target": r"Line 3",
                "replacement": "Inserted using alternative field names",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            lines = f.readlines()

        assert len(lines) == 6  # Originally 5 lines, one line inserted
        assert "Inserted using alternative field names\n" in lines[3]  # Inserted after Line 3

    def test_edit_file_field_mapping_delete_with_alternative_names(self):
        """Test delete operation using alternative field names."""
        operations = [{"type": "delete", "target": r"Line 2"}]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Line 2" not in content

    def test_edit_file_field_mapping_preserves_standard_names(self):
        """Test that field mapping does not affect standard field names."""
        operations = [
            {
                "operation_type": "replace",
                "pattern": r"Line 3",
                "content": "Using standard field names",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Using standard field names" in content
        assert "Line 3\n" not in content


class TestFindAndReplace:
    """Test the find_and_replace convenience function."""

    def setup_method(self):
        """Set up."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self.test_content = """Hello World
This is a test
Hello Universe
Goodbye World"""
        self.temp_file.write(self.test_content)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_find_and_replace_regex(self):
        """Test regex replacement."""
        result = find_and_replace(
            self.temp_file.name, r"Hello\s+\w+", "Hi Everyone", use_regex=True
        )

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Hi Everyone" in content
        assert "Hello World" not in content
        assert "Hello Universe" not in content

    def test_find_and_replace_literal(self):
        """Test literal replacement."""
        result = find_and_replace(self.temp_file.name, "Hello", "Hi", use_regex=False)

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Hi World" in content
        assert "Hi Universe" in content
        assert "Hello World" not in content
        assert "Hello Universe" not in content

    def test_find_and_replace_case_insensitive(self):
        """Test case-insensitive replacement."""
        # First create content containing mixed cases
        with open(self.temp_file.name, "w") as f:
            f.write("hello HELLO Hello")

        result = find_and_replace(
            self.temp_file.name, "hello", "hi", case_sensitive=False
        )

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert content == "hi hi hi"

    def test_find_and_replace_no_match(self):
        """Test the no-match case."""
        result = find_and_replace(
            self.temp_file.name, "NonExistentPattern", "Replacement"
        )

        assert result.success is False
        assert "No matches found for pattern" in result.message


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_replace_lines_by_number(self):
        """Test _replace_lines replacement by line number."""
        lines = ["Line 1\n", "Line 2\n", "Line 3\n"]
        operation = EditOperation(
            operation_type="replace", line_number=2, content="New Line 2"
        )

        result = _replace_lines(lines, operation)

        assert result.success is True
        assert lines[1] == "New Line 2\n"

    def test_replace_lines_by_pattern(self):
        """Test _replace_lines replacement by pattern."""
        lines = ["Line 1\n", "Line 2\n", "Line 3\n"]
        operation = EditOperation(
            operation_type="replace", pattern=r"Line 2", content="New Line 2"
        )

        result = _replace_lines(lines, operation)

        assert result.success is True
        assert lines[1] == "New Line 2\n"

    def test_insert_lines_by_number(self):
        """Test _insert_lines insertion by line number."""
        lines = ["Line 1\n", "Line 3\n"]
        operation = EditOperation(
            operation_type="insert", line_number=2, content="Line 2"
        )

        result = _insert_lines(lines, operation)

        assert result.success is True
        assert len(lines) == 3
        assert lines[1] == "Line 2\n"

    def test_delete_lines_by_number(self):
        """Test _delete_lines deletion by line number."""
        lines = ["Line 1\n", "Line 2\n", "Line 3\n"]
        operation = EditOperation(operation_type="delete", line_number=2)

        result = _delete_lines(lines, operation)

        assert result.success is True
        assert len(lines) == 2
        assert lines == ["Line 1\n", "Line 3\n"]


class TestEditFileFieldMapping:
    """Test class dedicated to edit_file field-mapping behavior."""

    def setup_method(self):
        """Set up before each test method."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        )
        self.test_content = """<html>
<head>
    <title>Original Title</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>"""
        self.temp_file.write(self.test_content)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up after each test method."""
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_field_mapping_html_style_replacement(self):
        """Test a typical HTML-style replace operation, simulating the original bug scenario."""
        operations = [
            {
                "type": "replace",
                "target": r"<head>",
                "replacement": '<head>\n <meta charset="UTF-8">\n <meta name="viewport" content="width=device-width, initial-scale=1.0">\n <title>Updated Title</title>\n',
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert '<meta charset="UTF-8">' in content
        assert '<meta name="viewport"' in content
        assert "Updated Title" in content

    def test_field_mapping_all_alternative_names(self):
        """Test mapping of all alternative field names."""
        operations = [
            {
                "type": "replace",
                "target": r"Hello World",
                "replacement": "Replaced Hello World",
            },
            {
                "type": "insert",
                "target": r"Hello World",
                "replacement": "    <!-- Inserted comment -->\n",
            },
            {
                "type": "delete",
                "target": r"</html>",
            },
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 3

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Replaced Hello World" in content
        assert "<!-- Inserted comment -->" in content
        assert "</html>" not in content

    def test_field_mapping_preserves_original_fields(self):
        """Test that original field names are unaffected by mapping."""
        operations = [
            {
                "operation_type": "replace",
                "pattern": r"Hello World",
                "content": "Using original fields",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Using original fields" in content

    def test_field_mapping_mixed_standard_and_alternative(self):
        """Test mixing standard and alternative field names within one operation."""
        operations = [
            {
                "type": "replace",  # Alternative field name
                "pattern": r"Hello World",  # Standard field name
                "replacement": "Mixed naming scheme",  # Alternative field name
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Mixed naming scheme" in content

    def test_field_mapping_with_line_number(self):
        """Test field mapping with a line number."""
        operations = [
            {
                "type": "replace",
                "line_number": 5,
                "replacement": "    <h1>Updated Heading</h1>",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            lines = f.readlines()

        assert "Updated Heading" in lines[4]

    def test_field_mapping_error_handling(self):
        """Test error handling in field mapping."""
        operations = [
            {
                "type": "replace",
                "target": r"NonExistentPattern",
                "replacement": "Some content",
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is False
        assert "No lines found matching pattern" in result.message

    def test_field_mapping_multiple_operations_different_naming(self):
        """Test multiple operations using different naming conventions."""
        operations = [
            {
                "type": "replace",
                "target": r"Original Title",
                "replacement": "New Title",
            },
            {
                "operation_type": "replace",
                "pattern": r"Hello World",
                "content": "Updated Greeting",
            },
            {
                "type": "insert",
                "line_number": 7,
                "replacement": "    <p>New paragraph</p>\n",
            },
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 3

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "New Title" in content
        assert "Updated Greeting" in content
        assert "<p>New paragraph</p>" in content

    def test_field_mapping_empty_operations(self):
        """Test field mapping with an empty operation list."""
        operations = []

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 0

    def test_field_mapping_unknown_fields_preserved(self):
        """Test that unknown fields are preserved."""
        operations = [
            {
                "type": "replace",
                "target": r"Hello World",
                "replacement": "Updated Hello",
                "unknown_field": "should_be_preserved",
                "another_unknown": 123,
            }
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Updated Hello" in content
