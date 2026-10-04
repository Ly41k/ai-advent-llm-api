"""Console presentation of saved evidence or a new live Day24 run.

The presentation never changes retrieval, model verdicts, or manual judgments.
Only --live calls Ollama. Saved mode reads reports and rechecks literal evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import textwrap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SAVED = HERE / "reports/console/evaluate_again_reviewed.json"
THRESHOLD = HERE / "reports/console/threshold_check_original.json"
GUIDE = {
    "positive-01": "Изоляция по dialogue ID; SQLite; восстановление выбранной истории.",
    "positive-02": "planning -> execution -> validation -> done; pause не пятая стадия.",
    "positive-03": "preflight до генерации; postflight после ответа, до сохранения.",
    "positive-04": "Утверждённый план перед execution; PASS перед done.",
    "positive-05": "stdio -> ClientSession -> initialize() -> list_tools().",
    "positive-06": "Имя первого инструмента: get_github_repo.",
    "positive-07": "worker.py собирает GitHub-данные; агент читает сохранённую сводку.",
    "positive-08": "search_repository -> summarize_repository -> save_report.",
    "positive-09": "Маршрутизация github/analysis/storage; read_report -> verify_report.",
    "positive-10": "Не только active: повторные запуски / свежие сводки в журнале или БД.",
    "negative-01": "Похожий контекст не содержит выручку: нельзя придумывать сумму.",
    "negative-02": "Все кандидаты ниже рабочего порога: не знаю + уточнение.",
}


def read_json(path):
    def invalid(value):
        raise ValueError(f"Недопустимое JSON-число: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def source_path(root, name):
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Источник находится вне репозитория")
    return path


def check_evidence(result, root=ROOT):
    """Independent literal/provenance checks; never infer semantic completeness."""
    errors = []
    hits = {h["chunk_id"]: h for h in result["retrieval"]["sources"]}
    sources = {s["id"]: s for s in result["sources"]}
    claims = {c["id"]: c for c in result["claims"]}
    catalog = result["retrieval"].get("quote_catalog", {})
    if len(sources) != len(result["sources"]) or len(claims) != len(result["claims"]):
        errors.append("Повторяющиеся ID источников или утверждений")
    verified = 0
    for quote in result["quotes"]:
        try:
            hit = hits[quote["chunk_id"]]
            source = sources[quote["source_id"]]
            claim = claims[quote["claim_id"]]
            text = source_path(root, hit["source"]).read_text(encoding="utf-8").replace("\r\n", "\n").strip()
            lines = text.splitlines(keepends=True)
            bounds = "".join(lines[hit["start_line"] - 1:hit["end_line"]])
            if not (1 <= hit["start_line"] <= hit["end_line"] <= len(lines)) or hit["text"] not in bounds:
                raise ValueError("Текст чанка не найден в заявленных строках файла")
            for key in ("chunk_id", "source", "section", "start_line", "end_line"):
                if source[key] != hit[key]:
                    raise ValueError(f"Метаданные источника не совпадают: {key}")
            for key in ("chunk_id", "source", "section"):
                if quote[key] != hit[key]:
                    raise ValueError(f"Метаданные цитаты не совпадают: {key}")
            literal = quote["quote"]
            if not literal or literal not in hit["text"] or literal not in text:
                raise ValueError("Цитата не является дословным фрагментом чанка и файла")
            entry = catalog[quote["quote_id"]]
            if entry["quote"] != literal or entry["chunk_id"] != hit["chunk_id"]:
                raise ValueError("quote_id не соответствует цитате/чанку")
            start = hit["start_line"] + hit["text"].count("\n", 0, hit["text"].index(literal))
            if quote["start_line"] != start or quote["end_line"] != start + literal.count("\n"):
                raise ValueError("Неверные номера строк цитаты")
            refs = claim["citations"]
            expected_ref = {k: v for k, v in quote.items() if k not in ("claim_id", "source_id")}
            if claim["text"] != literal or refs != [expected_ref]:
                raise ValueError("Утверждение не совпадает со своей единственной цитатой")
            verified += 1
        except (KeyError, ValueError, OSError, TypeError) as error:
            errors.append(f"Цитата {quote.get('quote_id', '?')}: {error}")
    if result["status"] == "answered":
        if not sources or not claims or not result["quotes"]:
            errors.append("Содержательный ответ без обязательных доказательств")
        if len(claims) != len(result["quotes"]):
            errors.append("Не у каждого утверждения одна цитата")
        if set(sources) != {q["source_id"] for q in result["quotes"]}:
            errors.append("Источник без связанной цитаты")
        if set(claims) != {q["claim_id"] for q in result["quotes"]}:
            errors.append("Утверждение без связанной цитаты")
        # Match the published answer, including citation markers/code fences,
        # rather than trusting the recorded verbatim_answer flag.
        parts = []
        for claim in result["claims"]:
            refs = [q for q in result["quotes"] if q["claim_id"] == claim["id"]]
            if len(refs) != 1:
                continue
            rendered = claim["text"]
            if refs[0]["source"].endswith(".py") and "```" not in rendered:
                rendered = "```python\n" + rendered + "\n```"
            separator = "\n" if rendered.rstrip().endswith(("```", "~~~")) else " "
            parts.append(rendered + separator + f"[{refs[0]['source_id']}]")
        if result["answer"] != "\n".join(parts):
            errors.append("Публичный ответ изменён относительно подтверждённых фрагментов")
    else:
        if result["status"] != "unknown" or not result["clarification"]:
            errors.append("Некорректный отказ или отсутствует просьба уточнить")
        if sources or claims or result["quotes"]:
            errors.append("Отказ содержит фиктивные доказательства")
        answer = result["answer"].casefold()
        if "не знаю" not in answer and "don't know" not in answer:
            errors.append("В отказе нет сообщения 'не знаю'")
    return {"ok": not errors, "verified_quotes": verified, "errors": errors}


def check_threshold(result):
    trace = result["retrieval"]
    threshold = trace["settings"]["min_similarity"]
    scores = [c["cosine"] for c in trace["candidates"]]
    maximum = max(scores) if scores else None
    valid = (result["status"] == "unknown" and result["reason"] == "below_threshold"
             and (maximum is None or maximum < threshold)
             and trace["eligible_count"] == trace["selected_count"] == 0
             and result["validation"]["attempts"] == 0
             and not result["validation"]["model_calls"])
    return valid, maximum, threshold


class Console:
    def __init__(self, pause=True):
        self.pause = pause and sys.stdin.isatty()
        size = shutil.get_terminal_size((92, 30))
        self.width = max(50, min(size.columns - 2, 100))
        self.page = max(10, min(size.lines - 5, 25))

    def block(self, title, text):
        print("\n" + "=" * self.width, flush=True)
        print(title, flush=True)
        print("-" * self.width, flush=True)
        lines = []
        for line in str(text).splitlines():
            lines.extend(textwrap.wrap(line, self.width, replace_whitespace=False,
                                       drop_whitespace=False) or [""])
        for index, line in enumerate(lines, 1):
            print(line, flush=True)
            if self.pause and index % self.page == 0 and index < len(lines):
                input("[Enter: следующая часть; Ctrl+C: остановить] ")
        if self.pause:
            input("[Enter: следующий экран; Ctrl+C: остановить] ")


def present(row, console):
    result = row["result"]
    trace = result["retrieval"]
    scores = [c["cosine"] for c in trace["candidates"]]
    maximum = f"{max(scores):.6f}" if scores else "нет кандидатов"
    console.block(f"ВОПРОС {row['id']}",
                  f"{row['question']}\n\nНа что смотреть: {GUIDE.get(row['id'], row.get('expectation', ''))}\n"
                  f"Порог: {trace['settings']['min_similarity']}; max cosine: {maximum}\n"
                  f"Кандидатов: {trace['candidate_count']}; прошли порог: {trace['eligible_count']}; "
                  f"выбрано: {trace['selected_count']}")
    console.block(f"{row['id']} — ОТВЕТ (полный исходный текст)",
                  f"status={result['status']}; reason={result['reason']}\n\n{result['answer']}"
                  + (f"\n\nУТОЧНЕНИЕ:\n{result['clarification']}" if result['clarification'] else ""))
    lines = []
    for source in result["sources"]:
        lines.extend([f"[{source['id']}] source: {source['source']}",
                      f"    section: {source['section']}", f"    chunk_id: {source['chunk_id']}",
                      f"    строки: {source['start_line']}–{source['end_line']}; cosine={source['cosine']:.6f}"])
    console.block(f"{row['id']} — ИСТОЧНИКИ", "\n".join(lines) or "sources=[] — при отказе это правильно.")
    for quote in result["quotes"]:
        console.block(f"{row['id']} — ЦИТАТА {quote['quote_id']} -> источник [{quote['source_id']}]",
                      f"Утверждение {quote['claim_id']}; {quote['source']}\n"
                      f"section: {quote['section']}; chunk_id: {quote['chunk_id']}\n"
                      f"строки цитаты: {quote['start_line']}–{quote['end_line']}\n\n{quote['quote']}")
    checks = check_evidence(result)
    validation = result["validation"]
    model = "ДА" if validation["coverage_supported"] else "НЕТ / НЕ ВЫПОЛНЯЛСЯ"
    review = row.get("manual_review", {})
    manual = ("ПОДТВЕРЖДЕНО В СОХРАНЁННОЙ РУЧНОЙ ПРОВЕРКЕ"
              if review.get("answer_matches_quotes") is True and review.get("fully_answers_question") is True
              else "РУЧНАЯ ПРОВЕРКА НЕ ЗАПОЛНЕНА")
    lines = [f"Повторная проверка текста, файлов и связей: {'PASS' if checks['ok'] else 'FAIL'}",
             f"Дословных цитат проверено: {checks['verified_quotes']}/{len(result['quotes'])}",
             f"Модельный аудит полноты: {model}",
             f"manual_review_required (оценка программы): {validation.get('manual_review_required', False)}",
             f"Вызовов модели: {len(validation['model_calls'])}; попыток: {validation['attempts']}"]
    if row["answerable"]:
        lines.extend([f"Смысл и полнота: {manual}",
                      "Дословность проверяется кодом; смысл и полнота требуют чтения источников."])
    else:
        lines.append("Правильный контрольный отказ: " + ("ДА" if checks["ok"] and result["status"] == "unknown" else "НЕТ"))
    if review.get("notes"):
        lines.append("Запись ручной проверки: " + review["notes"])
    for verdict in (validation.get("coverage_verdict") or {}).get("checks", []):
        lines.append(f"Аудитор [{verdict['id']}], covered={verdict['covered']}: {verdict['reason']}")
    lines.extend(checks["errors"])
    console.block(f"{row['id']} — ПРОВЕРКИ И ПОЯСНЕНИЕ", "\n".join(lines))
    return checks


def totals(report, checks, threshold_ok):
    rows = report["details"]
    positives = [(r, c) for r, c in zip(rows, checks) if r["answerable"]]
    negatives = [(r, c) for r, c in zip(rows, checks) if not r["answerable"]]
    answered = sum(r["result"]["status"] == "answered" for r, _ in positives)
    evidence = sum(c["ok"] and r["result"]["status"] == "answered" for r, c in positives)
    manual = sum(c["ok"] and r["result"]["status"] == "answered"
                 and r.get("manual_review", {}).get("answer_matches_quotes") is True
                 and r.get("manual_review", {}).get("fully_answers_question") is True for r, c in positives)
    refusals = sum(c["ok"] and r["result"]["status"] == "unknown" for r, c in negatives)
    below = [(r, c) for r, c in negatives if r["result"]["reason"] == "below_threshold"]
    regular_threshold = any(c["ok"] and check_threshold(r["result"])[0] for r, c in below)
    return {"positive_questions": len(positives), "answers": answered, "source_quote_contract": evidence,
            "quotes_verified": sum(c["verified_quotes"] for _, c in positives),
            "model_coverage": sum(r["result"]["validation"]["coverage_supported"] for r, _ in positives),
            "recorded_manual_complete": manual, "negative_questions": len(negatives), "correct_refusals": refusals,
            "working_threshold_verified": regular_threshold, "experiment_threshold_verified": threshold_ok,
            "assignment_review_complete": len(positives) == 10 and manual == evidence == answered == 10
            and len(negatives) == refusals == 2 and regular_threshold and threshold_ok}


def live_run(args, console):
    from evaluate24 import evaluate, load_questions, save_report
    from grounded_agent import StructuredOllama
    from strict_agent import StrictRAGAgent
    from support24 import KnowledgeBase, Settings
    report_path = args.report or HERE / "reports/check/console_live.json"
    threshold_path = args.threshold_report or HERE / "reports/check/console_live_threshold.json"
    if report_path.resolve() == threshold_path.resolve():
        raise ValueError("Для полного отчёта и теста порога нужны разные файлы")
    checkpoints = report_path.parent / (report_path.stem + "_answers")
    if report_path.exists() or report_path.with_suffix('.md').exists() or threshold_path.exists() or checkpoints.exists():
        raise ValueError("Выходной файл уже существует; укажите новые --report и --threshold-report")
    kb = KnowledgeBase(args.db)
    checks = []
    try:
        provider = StructuredOllama(args.url, "bge-m3", "qwen2.5:14b", num_ctx=16384,
                                    num_predict=2500, timeout=600)
        agent = StrictRAGAgent(kb, provider, Settings(20, 5, .50, "fixed", "heuristic"),
                               coverage_policy="diagnostic", progress=lambda s: print(s, flush=True))
        items = load_questions()

        class StreamingAgent:
            def ask(self, question):
                row = items[len(checks)]
                print(f"\nOllama: {row['id']} — {question}", flush=True)
                result = agent.ask(question)
                # Save every completed response before presentation pauses.
                checkpoint = report_path.parent / (report_path.stem + "_answers") / (row['id'] + '.json')
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                checkpoint.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                checks.append(present({**row, "result": result.to_dict(), "manual_review": {}}, console))
                return result

        report = evaluate(StreamingAgent(), items)
        save_report(report_path, report)
        question = next(i["question"] for i in items if i["id"] == "positive-07")
        threshold_agent = StrictRAGAgent(kb, provider, Settings(20, 5, .99, "fixed", "heuristic"),
                                         coverage_policy="diagnostic", progress=lambda s: print(s, flush=True))
        threshold = threshold_agent.ask(question).to_dict()
        threshold_path.parent.mkdir(parents=True, exist_ok=True)
        threshold_path.write_text(json.dumps(threshold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report, threshold, checks, report_path, threshold_path
    finally:
        kb.close()


def main():
    parser = argparse.ArgumentParser(description="День24: все доказательства и отказы в консоли")
    parser.add_argument("--live", action="store_true", help="Новый реальный прогон Ollama; без флага просмотр сохранённых отчётов")
    parser.add_argument("--report", type=Path, help="Saved: входной evaluate JSON; live: новый выходной JSON")
    parser.add_argument("--threshold-report", type=Path, help="Saved: входной threshold JSON; live: новый выходной JSON")
    parser.add_argument("--no-pause", action="store_true", help="Вывести всё без Enter, удобно для журнала")
    parser.add_argument("--db", type=Path, default=ROOT / "day-21-document-indexing/knowledge.db")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    console = Console(not args.no_pause)
    try:
        console.block("ДЕНЬ24 — КОНСОЛЬНАЯ ДЕМОНСТРАЦИЯ", (
            "РЕЖИМ: НОВЫЙ LIVE ПРОГОН OLLAMA. Каждый ответ появится после генерации.\n"
            "Новые ответы требуют собственной ручной проверки; старые оценки не переносятся."
            if args.live else
            "РЕЖИМ: ПРОСМОТР СОХРАНЁННОГО РЕАЛЬНОГО ПРОГОНА.\n"
            "Ollama сейчас не вызывается. Это демонстрация ранее полученных результатов,\n"
            "с повторной проверкой цитат и файлов на этом компьютере."))
        if args.live:
            report, threshold, checks, report_path, threshold_path = live_run(args, console)
        else:
            report_path = args.report or SAVED
            threshold_path = args.threshold_report or THRESHOLD
            report, threshold = read_json(report_path), read_json(threshold_path)
            console.block("ОТКУДА ВЗЯТЫ РЕЗУЛЬТАТЫ", f"Полный отчёт: {report_path}\n"
                          f"SHA256: {hashlib.sha256(report_path.read_bytes()).hexdigest()}\n"
                          f"Эксперимент порога: {threshold_path}\n"
                          "Встроенный reviewed отчёт: ручная проверка ассистентом, не независимым человеком.\n"
                          "Свои входные отчёты не получают ручные оценки из встроенного отчёта.")
            trace = report['details'][0]['result']['retrieval']
            console.block("МОДЕЛИ И НАСТРОЙКИ СОХРАНЁННОГО ПРОГОНА", "\n".join([
                f"Embedding: {trace['index']['model']}; размерность: {trace['index']['dimension']}",
                f"Answer: {trace['answer_model']}; auditor: {trace['verifier_model']}",
                f"Протокол: {trace['grounding_protocol']}; coverage policy: {trace['coverage_policy']}",
                f"Стратегия: {trace['settings']['strategy']}; rewrite: {trace['settings']['rewrite_method']}",
                f"candidate_k={trace['settings']['candidate_k']}; final_k={trace['settings']['final_k']}",
                "negative coverage в diagnostic сохраняется и требует ручного рассмотрения."]))
            checks = [present(row, console) for row in report["details"]]
        threshold_row = {"id": "threshold-experiment", "question": threshold["question"], "answerable": False,
                         "expectation": "Тот же вопрос о worker: временный порог 0.99, рабочий порог 0.50.", "result": threshold}
        threshold_checks = present(threshold_row, console)
        threshold_ok, maximum, value = check_threshold(threshold)
        threshold_ok = threshold_ok and threshold_checks["ok"]
        console.block("ЭКСПЕРИМЕНТ ПОРОГА — ДЕТЕРМИНИРОВАННЫЙ ОТКАЗ", f"max cosine={maximum}; порог={value}\n"
                      f"below_threshold + 0 выбранных чанков + 0 вызовов модели: {'PASS' if threshold_ok else 'FAIL'}\n"
                      "0.99 — эксперимент, а не изменение рабочего порога.")
        summary = totals(report, checks, threshold_ok)
        console.block("ИТОГ ПО КАЖДОМУ ТРЕБОВАНИЮ", "\n".join([
            f"Ответы: {summary['answers']}/{summary['positive_questions']}",
            f"Источники source+section+chunk_id, цитаты и их связи: {summary['source_quote_contract']}/{summary['positive_questions']}",
            f"Дословных опубликованных цитат проверено: {summary['quotes_verified']}",
            f"Модельный аудит полноты: {summary['model_coverage']}/{summary['positive_questions']}",
            f"Смысл И полнота — сохранённая ручная проверка: {summary['recorded_manual_complete']}/{summary['positive_questions']}",
            f"Правильные контрольные отказы с уточнением: {summary['correct_refusals']}/{summary['negative_questions']}",
            f"Рабочий порог проверен: {summary['working_threshold_verified']}",
            f"Отдельный эксперимент порога проверен: {summary['experiment_threshold_verified']}",
            "Исходный summary.assignment_complete: " + str(report['summary']['assignment_complete']),
            ("Итог: требования подтверждены для показанного отчёта с записанной ручной проверкой."
             if summary['assignment_review_complete'] else
             "Итог: завершение не подтверждено; проверьте ошибки и заполните ручную проверку каждого нового ответа."),
            "Дословность не доказывает релевантность и полноту на любых будущих вопросах.",
            f"Отчёты: {report_path}; {threshold_path}"]))
        return 0 if all(c["ok"] for c in checks) and threshold_ok else 1
    except KeyboardInterrupt:
        print("\nДемонстрация остановлена. Завершённые live ответы сохранены отдельно.")
        return 130
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        print(f"\nОШИБКА: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
