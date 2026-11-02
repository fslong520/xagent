"""
Template utilities - helper functions for creating the template_manager.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .manager import TemplateManager


def create_template_manager(templates_root: Optional[Path] = None) -> "TemplateManager":
    """
    Create a template_manager (not initialized).

    Args:
        templates_root: optional path to the templates directory; defaults to
            the built-in path.

    Returns:
        TemplateManager instance (not initialized).
    """
    from .manager import TemplateManager

    # Default templates directory.
    if templates_root is None:
        templates_root = Path(__file__).parent / "built_in"

    # Create the template_manager (not initialized).
    template_manager = TemplateManager(templates_root=templates_root)

    return template_manager
