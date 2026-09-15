"""Загрузка постоянного профиля и инвариантов из JSON."""

import json
from pathlib import Path

from models import Profile


class ConfigurationError(RuntimeError):
    pass


class ConfigurationLoader:
    def __init__(self, config_directory: Path) -> None:
        self._config_directory = config_directory

    def load_profile(self) -> Profile:
        data = self._load_json("profile.json")
        try:
            return Profile(
                name=data["name"],
                role=data["role"],
                user_name=data["user_name"],
                language=data["language"],
                style=list(data["style"]),
                constraints=list(data["constraints"]),
            )
        except (KeyError, TypeError) as error:
            raise ConfigurationError(f"Некорректный profile.json: {error}") from error

    def load_invariants(self) -> dict:
        data = self._load_json("invariants.json")
        required = {"stack", "architecture", "rules"}
        missing = required - data.keys()
        if missing:
            raise ConfigurationError(
                "В invariants.json отсутствуют разделы: " + ", ".join(sorted(missing))
            )
        return data

    def _load_json(self, name: str) -> dict:
        path = self._config_directory / name
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigurationError(f"Не удалось загрузить {path}: {error}") from error
        if not isinstance(data, dict):
            raise ConfigurationError(f"{path} должен содержать JSON-объект")
        return data
