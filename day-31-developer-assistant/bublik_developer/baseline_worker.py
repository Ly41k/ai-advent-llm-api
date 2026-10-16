"""Dedicated benchmark worker; standard model worker rejects its context."""
from .baseline import BaselineQwen, validate_baseline_context
from .model_worker import main

if __name__ == "__main__":
    raise SystemExit(main(client_class=BaselineQwen, context_validator=validate_baseline_context))
