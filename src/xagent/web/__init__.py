"""xagent web module.

This module provides the xagent web interface, including:
- REST API endpoints
- WebSocket realtime communication
- Frontend user interface
- Monitoring and management

Usage:
    # Start from the command line
    python -m xagent.web

    # Start from code
    from xagent.web import run_server
    run_server(host="0.0.0.0", port=8000)
"""

from importlib.metadata import version
from typing import Any

try:
    __version__ = version("xagent")
except Exception:
    __version__ = "0.0.0+unknown"


def run_server(
    host: str = "127.0.0.1", port: int = 8000, reload: bool = False, **kwargs: Any
) -> None:
    """Start the web server quickly.

    Args:
        host: Server host address
        port: Server port
        reload: Whether to enable auto-reload
        **kwargs: Extra uvicorn arguments
    """
    import uvicorn

    uvicorn.run("xagent.web.app:app", host=host, port=port, reload=reload, **kwargs)


__all__ = ["run_server", "__version__"]
