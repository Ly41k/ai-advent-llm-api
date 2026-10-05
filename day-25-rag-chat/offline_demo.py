"""Explicitly scripted Ollama HTTP stand-in; never a live-model quality result.

Uses the real corpus, chunker, SQLite search, HTTP client, citation validators,
conversation persistence and CLI-compatible evaluation. Lexical hash vectors
and scripted JSON decisions replace BGE-M3/Qwen only inside this test module.
"""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading

from support25 import HERE, ROOT, KnowledgeBase, Settings, StructuredOllama
from corpus import load_documents, revision
from chunking import chunk_documents
from embeddings import normalize
from chat_agent import ChatAgent
from chat_store import ChatStore
from evaluate25 import evaluate


def words(text):
    return re.findall(r"[\w]+", text.casefold())


def vector(text):
    values = [0.0] * 256
    for word in words(text):
        # Stable lexical vectors test cosine retrieval, not semantic quality.
        word = word[:6] if not word.isascii() else word
        slot = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % len(values)
        values[slot] += 5 if word.isdigit() else 1
    return normalize(values if any(values) else [1.0] + values[1:])


def data_from(prompt):
    return json.loads(prompt.rsplit("\nDATA:\n", 1)[1])


class ScriptedModel:
    def __init__(self):
        self.calls = []

    def respond(self, endpoint, body):
        self.calls.append((endpoint, body))
        if endpoint == "embed":
            return {"embeddings": [vector(text) for text in body["input"]]}
        schema = body["format"]
        # StructuredOllama appends a schema after the DATA JSON.
        prompt = body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0]
        data = data_from(prompt)
        properties = schema["properties"]
        if "resolved_question" in properties:
            message = data.get("current_message", data.get("current_request", ""))
            updates, question = [], []
            labels = {"Цель": "goal", "Ограничение": "constraints", "Уточнение": "clarifications", "Термин": "terms"}
            for line in message.splitlines():
                label, colon, content = line.partition(":")
                if colon and label in labels:
                    value, key = content.strip(), ""
                    if label == "Термин":
                        key, value = [part.strip() for part in value.split("=", 1)]
                    updates.append({"kind": labels[label], "key": key, "value": value, "evidence": content.strip()})
                else:
                    question.append(line)
            query = "\n".join(question)
            scope = re.findall(r"(?:день|дня|дне)\s+(\d+)", query, re.I)
            if not scope:
                history = json.dumps(data["recent_history"], ensure_ascii=False)
                scope = re.findall(r"(?:день|дня|дне)\s+(\d+)", history, re.I)
            if not scope:
                scope = re.findall(r"(?:день|дня|дне)\s+(\d+)", json.dumps(data["task_state"], ensure_ascii=False), re.I)
            resolved = f"День {scope[-1]}. {query}" if scope else query
            answer = {"resolved_question": resolved, "needs_clarification": False, "updates": updates}
        elif "quote_ids" in properties:
            question = data["question"]
            days = re.findall(r"(?:день|дня|дне)\s+(\d+)", question, re.I)
            day = int(days[-1]) if days else None
            tokens = set(words(question)) - {"день", "дня", "дне", "что", "как", "какой", "какие", "где", "на", "а", "у", "его", "это"}
            options = []
            for chunk in data["chunks"]:
                if day and chunk["course_lesson"] != day:
                    continue
                for quote in chunk["quotes"]:
                    score = len(tokens & set(words(quote["text"]))) + (0.2 if chunk["source"].endswith(".ru.md") else 0)
                    options.append((score, quote["quote_id"]))
            options.sort(reverse=True)
            ids = [ident for _, ident in options[:3]]
            # Obey the extractive fixture protocol: a selected lead-in must be
            # followed by its source command. This is scripted dependency
            # handling, not a claim about live semantic selection quality.
            dependencies, captions = {}, {}
            for chunk in data["chunks"]:
                for before, after in zip(chunk["quotes"], chunk["quotes"][1:]):
                    if (before["text"].rstrip().endswith(":")
                            and not before["text"].lstrip().startswith(("#", "```", "~~~"))
                            and after["text"].lstrip().startswith(("```", "~~~"))):
                        dependencies[before["quote_id"]] = after["quote_id"]
                        if (re.match(r"(?:```|~~~)(?:text|plaintext|mermaid)\s*\n", after["text"], re.I)
                                and re.search(r"→|->|=>", after["text"])):
                            captions[after["quote_id"]] = before["quote_id"]
            valid_sets = properties["quote_ids"].get("enum")
            if valid_sets is not None:
                # This fixture chooses a schema-admissible source subset. It
                # still does not model relevance/coverage quality of Qwen.
                ids = max(valid_sets, key=lambda choice: (len(set(choice) & set(ids)), -len(choice)))
            else:
                selected = set(ids)
                for ident in ids:
                    if ident in captions:
                        selected.add(captions[ident])
                for ident in list(selected):
                    if ident in dependencies:
                        selected.add(dependencies[ident])
                ids = [q["quote_id"] for chunk in data["chunks"] for q in chunk["quotes"] if q["quote_id"] in selected]
            answer = {"status": "answered" if ids else "unknown", "quote_ids": ids}
        elif "proof_ids" in properties:
            ids = properties["proof_ids"]["items"].get("enum", [])
            answer = {"reason": "Scripted protocol fixture; completeness requires live source review",
                      "proof_ids": ids[:1], "covered": bool(ids)}
        else:
            raise ValueError("Unexpected test schema")
        return {"response": json.dumps(answer, ensure_ascii=False), "done": True, "done_reason": "stop"}


@contextmanager
def http_fixture(model=None):
    model = model or ScriptedModel()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                payload = model.respond(self.path.rsplit("/", 1)[-1], body)
                encoded = json.dumps(payload).encode()
                self.send_response(200)
            except Exception as error:
                encoded = json.dumps({"error": str(error)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", model
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def fixture_index(path):
    kb = KnowledgeBase(path)
    docs = load_documents(ROOT)
    for strategy in ("fixed", "structural"):
        chunks = chunk_documents(docs, strategy, 500, 75)
        kb.save(docs, strategy, chunks, [vector(c.text) for c in chunks],
                "fixture-hash-256", 500, 75, revision(ROOT))
    return kb


def run_demo(output=None):
    with tempfile.TemporaryDirectory() as temp, http_fixture() as (url, model):
        temp = Path(temp)
        kb = fixture_index(temp / "knowledge.db")
        store = ChatStore(temp / "chats.db")
        provider = StructuredOllama(url, "fixture-hash-256", "scripted-fixture", num_ctx=32768)
        agent = ChatAgent(store, kb, provider, Settings(40, 20, 0.0, "fixed", "heuristic"))

        def restart():
            agent.store.close()
            agent.kb.close()
            agent.store = ChatStore(temp / "chats.db")
            agent.kb = KnowledgeBase(temp / "knowledge.db")

        try:
            report = evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", restart)
            report["fixture"] = {"embedding_model": "fixture-hash-256", "answer_model": "scripted-fixture",
                "http_calls": len(model.calls), "embedding_calls": sum(e == "embed" for e, _ in model.calls),
                "corpus_revision": revision(ROOT), "source": "actual repository corpus",
                "warning": "Scripted planning/coverage and hash embeddings. This is NOT a real-model quality evaluation."}
        finally:
            agent.store.close()
            agent.kb.close()
    output = Path(output or HERE / "reports/check/offline.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    report = run_demo()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["summary"]["all_checks_pass"] else 1)
