"""A persistent conversation around the Day 24 strict, extractive RAG pipeline."""
import json
from support25 import Day23RAGAgent, Settings, StrictRAGAgent, refusal
from conversation import ContextProvider, plan, recent_context
from memory import public_state, update
from retrieval25 import LessonRetriever
from requirements25 import coverage_requirements25


class ChatAgent:
    def __init__(self, store, kb, provider, settings=None, verifier=None,
                 history_turns=4, coverage_policy="strict", progress=None):
        if type(history_turns) is not int or not 1 <= history_turns <= 20:
            raise ValueError("history_turns must be 1–20")
        if coverage_policy not in ("strict", "diagnostic"):
            raise ValueError("Invalid coverage policy")
        self.store, self.kb, self.provider = store, kb, provider
        self.settings = settings or Settings(20, 5, 0.50, "fixed", "heuristic")
        self.verifier = verifier or provider
        self.history_turns, self.coverage_policy, self.progress = history_turns, coverage_policy, progress

    def ask(self, session, message):
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValueError("Message must contain 1–4000 characters")
        turn, current = self.store.begin(session, message)
        state = current["state"]
        try:
            history = recent_context(self.store.history(session, self.history_turns + 1))
            if self.progress:
                self.progress("Resolving question and task memory…")
            question, state, ambiguous, planning = plan(self.provider, message, state, history, turn)
            if not ambiguous and not state["goal"] and len(self.store.history(session, 2)) == 1:
                # The first actual request defines an initial objective even if
                # the planner proposes no goal. It is intent, not a repo fact.
                value = message[:600].strip()
                try:
                    state = update(state, "goal", "", value, value, message, turn,
                                   origin="initial_question")
                    planning["initial_goal_from_user_request"] = True
                except ValueError as error:
                    planning["warnings"].append(str(error))
            context = {"original_question": message, "task_state": public_state(state), "recent_history": history}
            provider = ContextProvider(self.provider, context, self.progress, bundle_sequences=True)
            verifier = ContextProvider(self.verifier, context)
            if self.progress:
                self.progress("Searching the knowledge base…")
            if ambiguous:
                # Even an ambiguous question triggers fresh RAG retrieval; no old evidence is reused.
                retrieval = LessonRetriever(self.kb, provider, self.settings).run(question, generate=False).to_dict()
                answer, clarification = refusal(message)
                result = {"status": "unknown", "answer": answer, "clarification": clarification,
                          "sources": [], "quotes": [], "claims": [], "validation": {},
                          "reason": "ambiguous_reference", "retrieval": retrieval}
            else:
                rag = StrictRAGAgent(self.kb, provider, self.settings, verifier,
                    coverage_policy=self.coverage_policy, progress=self.progress,
                    requirements_factory=coverage_requirements25)
                rag.retriever = LessonRetriever(self.kb, provider, self.settings)
                result = rag.ask(question).to_dict()
                if provider.selection_refinements:
                    result["validation"]["selection_refinements"] = provider.selection_refinements
                if provider.fragment_filters:
                    result["validation"]["fragment_filters"] = provider.fragment_filters
                if provider.source_unit_selections:
                    result["validation"]["source_unit_selections"] = provider.source_unit_selections
                if verifier.conditional_audits:
                    result["validation"]["conditional_audits"] = verifier.conditional_audits
                if verifier.route_audits:
                    result["validation"]["route_audits"] = verifier.route_audits
            if result["status"] == "unknown":
                # A generic Day 24 hint can ask for a lesson already supplied.
                # This is UI wording only; verdict/evidence/retrieval stay intact.
                result["clarification"] = (
                    "Уточните, какой объект или предыдущую тему вы имеете в виду."
                    if ambiguous else
                    "Уточните запрос или добавьте в базу знаний источник, подтверждающий запрошенные данные."
                ) if any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in message) else (
                    "Clarify which object or previous topic you mean." if ambiguous else
                    "Clarify the request or add a source supporting the requested data to the knowledge base.")
            result.update(question=message, resolved_question=question, session_id=session, turn_id=turn,
                          task_state=state, conversation=planning)
            # Use the same JSON-compatible types for fresh, resumed and exported turns.
            result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        except (Exception, KeyboardInterrupt) as error:
            # Persist technical failure as failure, never as a source-less generated answer.
            self.store.finish(session, turn, current["version"], state, error=f"{type(error).__name__}: {error}")
            raise
        self.store.finish(session, turn, current["version"], state, response=result)
        return result


def render_response(result):
    lines = [result["answer"]]
    if result.get("clarification"):
        lines.append(result["clarification"])
    lines.append("\nИсточники / Sources:")
    if not result["sources"]:
        lines.append("Нет подтверждённых источников / No confirmed sources.")
    for row in result["sources"]:
        lines.append(f"[{row['id']}] {row['source']}:{row['start_line']}-{row['end_line']} | "
                     f"section={row['section']} | chunk_id={row['chunk_id']} | cosine={row['cosine']:.4f}")
    if result.get("validation", {}).get("manual_review_required"):
        lines.append("Проверка полноты не пройдена: требуется просмотр источников. / Coverage requires manual review.")
    for warning in result.get("conversation", {}).get("warnings", []):
        lines.append("Memory/resolution warning: " + warning)
    return "\n".join(lines)
