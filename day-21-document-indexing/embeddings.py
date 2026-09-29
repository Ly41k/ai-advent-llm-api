"""Local Ollama embedding and generation APIs; no Groq key is needed."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def normalize(vector: list[float]) -> list[float]:
    if not vector or any(not math.isfinite(x) for x in vector):
        raise ValueError("Embedding contains no values or non-finite values")
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise ValueError("Zero embedding")
    return [x / norm for x in vector]


class Ollama:
    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 embedding_model: str = "bge-m3", answer_model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = embedding_model
        self.answer_model = answer_model

    def _post(self, endpoint: str, body: dict) -> dict:
        request = Request(f"{self.base_url}/api/{endpoint}",
                          data=json.dumps(body).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=180) as response:
                return json.load(response)
        except (HTTPError, URLError) as error:
            raise RuntimeError(f"Ollama {endpoint} failed: {error}; check ollama serve and models") from error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._post("embed", {"model": self.model, "input": texts})
        vectors = result.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise RuntimeError("Ollama returned an unexpected number of embeddings")
        normalized = [normalize(v) for v in vectors]
        if len({len(v) for v in normalized}) != 1:
            raise RuntimeError("Ollama returned inconsistent embedding dimensions")
        return normalized

    def answer(self, prompt: str) -> str:
        result = self._post("generate", {"model": self.answer_model,
                                          "prompt": prompt, "stream": False,
                                          "options": {"temperature": 0}})
        return result["response"].strip()
