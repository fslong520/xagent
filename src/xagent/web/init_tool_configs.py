"""Initialize tool configurations in database."""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from .models.database import get_db
from .models.tool_config import ToolConfig

logger = logging.getLogger(__name__)


def get_default_tool_configs() -> list[Dict[str, Any]]:
    """Get default tool configurations."""
    return [
        {
            "tool_name": "python_executor",
            "tool_type": "builtin",
            "category": "development",
            "display_name": "Python Code Executor",
            "description": "Run Python code for data analysis and computation tasks",
            "enabled": True,
            "config": {"working_dir": "/workspace/output"},
            "dependencies": [],
        },
        {
            "tool_name": "bash",
            "tool_type": "builtin",
            "category": "development",
            "display_name": "Bash Command Executor",
            "description": "Run Bash commands for system operations and file management",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "web_search",
            "tool_type": "builtin",
            "category": "search",
            "display_name": "Google Web Search",
            "description": "Search the web using the Google search engine",
            "enabled": True,
            "requires_configuration": True,
            "config": {
                "provider": "google",
                "api_key_env": "GOOGLE_API_KEY",
                "cse_id_env": "GOOGLE_CSE_ID",
            },
            "dependencies": ["google_api_key", "google_cse_id"],
        },
        {
            "tool_name": "tavily_web_search",
            "tool_type": "builtin",
            "category": "search",
            "display_name": "Tavily Web Search",
            "description": "Search the web with the Tavily Search API; no Google account required",
            "enabled": True,
            "requires_configuration": True,
            "config": {
                "provider": "tavily",
                "api_key_env": "TAVILY_API_KEY",
            },
            "dependencies": ["tavily_api_key"],
        },
        {
            "tool_name": "exa_web_search",
            "tool_type": "builtin",
            "category": "search",
            "display_name": "Exa AI Search",
            "description": "AI-powered web search using Exa, with content extraction and category filtering",
            "enabled": True,
            "requires_configuration": True,
            "config": {
                "provider": "exa",
                "api_key_env": "EXA_API_KEY",
            },
            "dependencies": ["exa_api_key"],
        },
        {
            "tool_name": "zhipu_web_search",
            "tool_type": "builtin",
            "category": "search",
            "display_name": "Zhipu Web Search",
            "description": "Search the web using the Zhipu Web Search API",
            "enabled": True,
            "requires_configuration": True,
            "config": {
                "provider": "zhipu",
                "api_key_env": "ZHIPU_API_KEY",
                "base_url_env": "ZHIPU_BASE_URL",
            },
            "dependencies": ["zhipu_api_key"],
        },
        {
            "tool_name": "sql_query",
            "tool_type": "builtin",
            "category": "database",
            "display_name": "SQL Query",
            "description": "Run SQL queries against the data sources configured for the current user",
            "enabled": True,
            "requires_configuration": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "fetch_webpage",
            "tool_type": "builtin",
            "category": "search",
            "display_name": "Web Page Fetch",
            "description": "Fetch web page content with text extraction and parsing",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "calculator",
            "tool_type": "builtin",
            "category": "development",
            "display_name": "Calculator",
            "description": "Perform math calculations and expression evaluation",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "read_file",
            "tool_type": "file",
            "category": "file_operations",
            "display_name": "Read File",
            "description": "Read file contents; supports multiple file formats",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "write_file",
            "tool_type": "file",
            "category": "file_operations",
            "display_name": "Write File",
            "description": "Write file contents; supports multiple file formats",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "list_directory",
            "tool_type": "file",
            "category": "file_operations",
            "display_name": "List Directory",
            "description": "List directory contents with file filtering and sorting",
            "enabled": True,
            "config": {},
            "dependencies": [],
        },
        {
            "tool_name": "vision_tool",
            "tool_type": "vision",
            "category": "ai_tools",
            "display_name": "Vision Analysis",
            "description": "Analyze image content with image recognition and understanding",
            "enabled": True,
            "config": {},
            "dependencies": ["vision_model"],
        },
        {
            "tool_name": "image_generation",
            "tool_type": "image",
            "category": "ai_tools",
            "display_name": "Image Generation",
            "description": "Generate images from text descriptions",
            "enabled": True,
            "config": {},
            "dependencies": ["image_model"],
        },
    ]


def init_tool_configs(db: Session) -> None:
    """Initialize tool configurations in database."""
    logger.info("Initializing tool configurations...")

    default_configs = get_default_tool_configs()

    for config_data in default_configs:
        # Check if tool config already exists
        existing = (
            db.query(ToolConfig)
            .filter(ToolConfig.tool_name == config_data["tool_name"])
            .first()
        )

        if existing:
            logger.info(
                f"Tool config '{config_data['tool_name']}' already exists, skipping..."
            )
            continue

        # Create new tool config
        tool_config = ToolConfig(**config_data)
        db.add(tool_config)
        logger.info(f"Added tool config: {config_data['tool_name']}")

    db.commit()
    logger.info("Tool configurations initialized successfully.")


def main() -> None:
    """Main function to initialize tool configurations."""
    logging.basicConfig(level=logging.INFO)

    db = next(get_db())
    try:
        init_tool_configs(db)
        print("Tool configurations initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize tool configurations: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
