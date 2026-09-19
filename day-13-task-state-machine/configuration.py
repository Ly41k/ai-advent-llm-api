"""Загрузка личности Бублика, пользовательских профилей и invariants."""

import json
from pathlib import Path

from models import AssistantIdentity, UserProfile


class ConfigurationError(RuntimeError):
    pass


class ConfigurationLoader:
    def __init__(self, config_directory: Path) -> None:
        self._config_directory = config_directory

    def load_assistant(self) -> AssistantIdentity:
        data = self._load_json("assistant.json")
        try:
            return AssistantIdentity(
                name=data["name"],
                role=data["role"],
            )
        except (KeyError, TypeError) as error:
            raise ConfigurationError(f"Некорректный assistant.json: {error}") from error

    def get_profiles(self) -> list[UserProfile]:
        directory = self._config_directory / "profiles"
        try:
            paths = sorted(directory.glob("*.json"))
        except OSError as error:
            raise ConfigurationError(f"Не удалось прочитать {directory}: {error}") from error
        if not paths:
            raise ConfigurationError(f"В {directory} нет пользовательских профилей")
        profiles = [self._load_profile(path) for path in paths]
        ids = [profile.id for profile in profiles]
        if len(ids) != len(set(ids)):
            raise ConfigurationError("ID пользовательских профилей должны быть уникальны")
        return profiles

    def load_profile(self, profile_id: str) -> UserProfile:
        for profile in self.get_profiles():
            if profile.id == profile_id:
                return profile
        raise ConfigurationError(f"Профиль {profile_id!r} не найден")

    @staticmethod
    def _load_profile(path: Path) -> UserProfile:
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
            return UserProfile(
                id=data["id"],
                name=data["name"],
                role=data["role"],
                language=data["language"],
                detail_level=data["detail_level"],
                style=list(data["style"]),
                response_format=list(data["response_format"]),
                constraints=list(data["constraints"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ConfigurationError(f"Некорректный профиль {path}: {error}") from error

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
