"""Deterministic structured-selector stand-in for token-free offline tests."""

import json
from types import SimpleNamespace


class OfflineModel:
    def __init__(self):
        self.chat = SimpleNamespace(completions=self)
        self.requests = []

    def create(self, *, messages, **kwargs):
        self.requests.append({**kwargs, "messages": messages})
        user_request, completed_line, _ = messages[1]["content"].split("\n", 2)
        user_request = user_request.removeprefix("Request: ")
        completed = json.loads(completed_line.removeprefix("Completed operations: "))
        if user_request.startswith("Get repository information for "):
            length = 1
        elif user_request.startswith("Summarize repository "):
            length = 2
        else:
            length = 5
        flow = ("FETCH", "SUMMARIZE", "SAVE", "READ", "VERIFY")
        if len(completed) >= length:
            raise RuntimeError("The agent requested more selections than the task requires")
        message = SimpleNamespace(content=json.dumps({"operation": flow[len(completed)]}))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
