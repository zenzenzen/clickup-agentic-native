"""Module runner that sends `python -m clickup_agent` through the CLI path."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
