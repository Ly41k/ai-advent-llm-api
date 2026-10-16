"""Checkout launcher; importing the CLI does not require MCP or a model."""
from bublik_developer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
