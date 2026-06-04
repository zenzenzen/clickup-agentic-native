"""ClickUp Agent package.

The package favors a generated-operation core plus curated wrappers that make
common ClickUp workflows safer for humans and LLM agents. Public entrypoints
live in the CLI and MCP server; support modules keep config, catalog lookup,
request building, and validation behavior shared.
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
