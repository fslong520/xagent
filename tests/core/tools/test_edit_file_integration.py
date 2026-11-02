"""
Integration tests for the edit_file tool.

Covers edit_file in realistic scenarios such as HTML editing and code changes.
"""

import os
import tempfile

from xagent.core.tools.core.file_tool import EditOperation, edit_file, find_and_replace


class TestEditFileIntegration:
    """Integration tests for the edit_file tool."""

    def setup_method(self):
        """Set up before each test method."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        )
        self.example_html = """<!DOCTYPE html>
<html>
<head>
    <title>My Website</title>
    <meta charset="UTF-8">
</head>
<body>
    <header>
        <h1>Welcome to My Website</h1>
        <nav>
            <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <main>
        <section id="home">
            <h2>Home Section</h2>
            <p>This is the home page content.</p>
        </section>

        <section id="about">
            <h2>About Section</h2>
            <p>Learn more about us.</p>
        </section>
    </main>

    <footer>
        <p>&copy; 2024 My Website</p>
    </footer>
</body>
</html>"""
        self.temp_file.write(self.example_html)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up after each test method."""
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_html_title_editing(self):
        """Test editing an HTML title."""
        operations = [
            EditOperation(
                operation_type="replace",
                line_number=4,
                content="    <title>My Awesome Website</title>",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "My Awesome Website" in content
        assert "<title>My Website</title>" not in content

    def test_html_navigation_addition(self):
        """Test adding an HTML navigation item."""
        operations = [
            EditOperation(
                operation_type="insert",
                pattern=r"<li><a href=\"#contact\">Contact</a></li>",
                content='                <li><a href="#services">Services</a></li>',
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert '<li><a href="#services">Services</a></li>' in content
        # Verify the navigation structure is intact
        nav_items = content.count("<li><a href=")
        assert nav_items == 4

    def test_html_content_update(self):
        """Test updating HTML content."""
        operations = [
            EditOperation(
                operation_type="replace",
                pattern=r"Learn more about us\.",
                content="Learn more about our amazing team and mission.",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "amazing team and mission" in content
        assert "Learn more about us." not in content

    def test_html_section_addition(self):
        """Test adding an HTML section."""
        operations = [
            EditOperation(
                operation_type="insert",
                pattern=r"Learn more about us\.</p>",
                content='        </section>\n        \n        <section id="services">\n            <h2>Services Section</h2>\n            <p>Our services content.</p>\n        </section>',
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed >= 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert '<section id="services">' in content
        assert "Services Section" in content
        assert "Our services content" in content

    def test_multiple_html_edits(self):
        """Test multiple HTML edit operations."""
        operations = [
            EditOperation(
                operation_type="replace",
                line_number=9,
                content="        <h1>Welcome to My Fantastic Website!</h1>",
            ),
            EditOperation(
                operation_type="insert",
                pattern=r"<li><a href=\"#about\">About</a></li>",
                content='                <li><a href="#blog">Blog</a></li>',
            ),
            EditOperation(
                operation_type="replace",
                pattern=r"This is the home page content\.",
                content="This is our amazing home page with new content.",
            ),
        ]

        result = edit_file(self.temp_file.name, operations, backup=True)

        assert result.success is True
        assert result.lines_changed == 3

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "Fantastic Website" in content
        assert '<li><a href="#blog">Blog</a></li>' in content
        assert "amazing home page" in content

        # Verify the backup file was created
        backup_file = self.temp_file.name + ".backup"
        assert os.path.exists(backup_file)

        with open(backup_file, "r") as f:
            backup_content = f.read()
        assert backup_content == self.example_html

    def test_find_and_replace_year_update(self):
        """Test find-and-replace for a year update."""
        result = find_and_replace(
            self.temp_file.name, r"2024", "2025", use_regex=True, backup=True
        )

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "&copy; 2025 My Website" in content
        assert "2024" not in content

    def test_find_and_replace_css_class_addition(self):
        """Test find-and-replace to add a CSS class."""
        # First add an element that needs to be modified
        with open(self.temp_file.name, "w") as f:
            modified_html = self.example_html.replace(
                "<h2>Home Section</h2>", '<h2 class="title">Home Section</h2>'
            )
            f.write(modified_html)

        result = find_and_replace(
            self.temp_file.name,
            r'class="title"',
            'class="title featured"',
            use_regex=True,
        )

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert 'class="title featured"' in content
        assert 'class="title"' not in content

    def test_html_meta_tag_addition(self):
        """Test adding an HTML meta tag."""
        operations = [
            EditOperation(
                operation_type="insert",
                pattern=r"<meta charset=\"UTF-8\">",
                content='    <meta name="description" content="My awesome website">\n    <meta name="keywords" content="website, awesome, cool">',
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 1

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert 'meta name="description"' in content
        assert 'meta name="keywords"' in content

    def test_html_structural_modifications(self):
        """Test modifying the HTML structure."""
        operations = [
            # Open the container div
            EditOperation(
                operation_type="replace",
                pattern=r"<body>",
                content="<body><div class='container'>",
            ),
            # Close the container div
            EditOperation(
                operation_type="replace",
                pattern=r"</body>",
                content="    </div>\n</body>",
            ),
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True
        assert result.lines_changed == 2

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "<div class='container'>" in content
        assert content.count("<div class='container'>") == 1
        assert content.count("</div>") >= 1

    def test_error_handling_invalid_pattern(self):
        """Test error handling for an invalid pattern."""
        operations = [
            EditOperation(
                operation_type="insert",
                pattern=r"[InvalidRegex[",
                content="Some content",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is False
        assert "failed" in result.message.lower()

    def test_case_sensitive_find_replace(self):
        """Test case-sensitive find-and-replace."""
        # First add content with mixed casing
        with open(self.temp_file.name, "w") as f:
            modified_html = self.example_html.replace(
                "Welcome to My Website", "Welcome to my WEBSITE"
            )
            f.write(modified_html)

        # Case-sensitive replacement should not match
        result = find_and_replace(
            self.temp_file.name, "MY WEBSITE", "My Awesome Website", case_sensitive=True
        )

        assert result.success is False

        # Case-insensitive replacement should match
        result = find_and_replace(
            self.temp_file.name,
            "MY WEBSITE",
            "My Awesome Website",
            case_sensitive=False,
        )

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()
        assert "My Awesome Website" in content

    def test_backup_and_recovery(self):
        """Test backup and restore behavior."""
        # Create an operation that will fail
        operations = [
            EditOperation(
                operation_type="replace",
                line_number=9999,  # Invalid line number, which makes the operation fail
                content="Some content",
            )
        ]

        result = edit_file(self.temp_file.name, operations, backup=True)

        assert result.success is False

        # Verify the original file was not modified
        with open(self.temp_file.name, "r") as f:
            content = f.read()
        assert content == self.example_html

        # A backup file may exist (created at operation start), but its content stays unchanged
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            with open(backup_file, "r") as f:
                backup_content = f.read()
            assert backup_content == self.example_html


class TestEditFileWithCode:
    """Test the edit_file tool on code files."""

    def setup_method(self):
        """Set up a Python code file."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        )
        self.example_code = '''#!/usr/bin/env python3
"""
Example Python module
"""

def hello_world():
    """Print hello world message."""
    print("Hello, World!")

def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    return a + b

if __name__ == "__main__":
    hello_world()
    result = calculate_sum(5, 3)
    print(f"Sum: {result}")
'''
        self.temp_file.write(self.example_code)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        backup_file = self.temp_file.name + ".backup"
        if os.path.exists(backup_file):
            os.remove(backup_file)

    def test_python_function_modification(self):
        """Test modifying a Python function."""
        operations = [
            EditOperation(
                operation_type="replace",
                pattern=r"def calculate_sum\(a, b\):",
                content="def calculate_sum(a, b, c=0):",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "def calculate_sum(a, b, c=0):" in content
        assert "def calculate_sum(a, b):" not in content

    def test_python_docstring_update(self):
        """Test updating a Python docstring."""
        operations = [
            EditOperation(
                operation_type="replace",
                pattern=r'"""Calculate sum of two numbers\."""',
                content='"""Calculate sum of numbers with optional third parameter."""',
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "optional third parameter" in content

    def test_python_import_addition(self):
        """Test adding a Python import."""
        operations = [
            EditOperation(
                operation_type="insert",
                pattern=r'"""',
                content="import os\nimport sys\n\n",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "import os" in content
        assert "import sys" in content

    def test_python_error_handling_update(self):
        """Test adding Python error handling."""
        operations = [
            EditOperation(
                operation_type="replace",
                pattern=r"return a \+ b",
                content="""try:
            return a + b + c
        except TypeError as e:
            print(f"Error: {e}")
            return None""",
            )
        ]

        result = edit_file(self.temp_file.name, operations)

        assert result.success is True

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        assert "try:" in content
        assert "except TypeError" in content
        # Check the original simple return statement was fully replaced
        lines = content.split("\n")
        simple_return_found = any(
            "return a + b" in line and "c" not in line for line in lines
        )
        assert not simple_return_found
