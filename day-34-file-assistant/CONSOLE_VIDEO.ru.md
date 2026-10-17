# Day 34 — сценарий видео в Mac Terminal, 5:40

Запись делает владелец. Все команды выполняются из корня репозитория в активной Python 3.13 venv. Не показывать `.env`, ключи, приватные receipts или raw HTTP. Новых Groq/OpenAI/Ollama-запросов нет. Команды читают публичные сохранённые материалы; verifier выполняет тесты и replay в temporary directory. Это демонстрация ранее принятой работы модели, не новая генерация.

## 0:00–0:40 — задание и архитектура

```bash
clear
sed -n '1,35p' day-34-file-assistant/README.ru.md
python3.13 day-34-file-assistant/main.py --help
```

Сказать: «Day 34 — ассистент файлов проекта. По цели пользователя реальная модель выбирает list, search, read, write и аргументы. Python проверяет действия, разрешает чтение закреплённых исходников Day 33 и создание Markdown только в новой папке Day 34. Два сценария, сохранённые документы, diff и replay. Здесь показываю сохранённые результаты без облачных вызовов».

## 0:40–1:40 — Usage: модельные решения и поиск

```bash
python3.13 - <<'PY'
import json
from pathlib import Path
t = json.loads(Path('day-34-file-assistant/evidence/usage-trace.json').read_text())
print('GOAL:', t['goal'])
print('PROVENANCE:', t['provenance']['kind'])
for n, call in enumerate(t['model_calls'], 1):
    decision = json.loads(call['response_text'])
    print('\nMODEL DECISION', n, 'HTTP', call['meta']['http_status'])
    for action in decision['actions']:
        args = action['args']
        if action['tool'] == 'write_file':
            args = {'path': args['path'], 'evidence_count': len(args['evidence'])}
        print(action['tool'], json.dumps(args, ensure_ascii=False))
search = next(e['result'] for e in t['events'] if e['action']['tool'] == 'search_files')
print('\nSEARCHED FILES:', len(search['searched_files']))
for match in search['matches']:
    print(f"{match['path']}:{match['line']} {match['text'].strip()}")
PY
```

Сказать: «Это проекция настоящих сохранённых решений; canonical requests и аргументы не заменены сценарием. Пять модельных решений, поиск по 17 файлам, десять совпадений в пяти исходниках. Видны выбранные моделью дополнительные чтения. В live приложение не диктовало последовательность. Offline-fixtures — отдельные сценарные тесты».

## 1:40–2:40 — Markdown, ссылки и diff

```bash
cat day-34-file-assistant/evidence/original/component-usage.md
sed -n '53,68p' day-33-support-assistant/mcp_client.py
cat day-34-file-assistant/evidence/historical/usage-changes.diff
shasum -a 256 day-34-file-assistant/evidence/original/component-usage.md
```

Сказать: «Отчёт различает одно определение, четыре импорта и пять вызовов. Ссылки — настоящие file:line, а цитаты сверяются дословно. Документ создан файловым инструментом, diff показывает создание. SHA фиксирует исходный результат».

## 2:40–3:40 — ADR: файловые операции и MCP

```bash
python3.13 - <<'PY'
import json
from pathlib import Path
t = json.loads(Path('day-34-file-assistant/evidence/adr-trace.json').read_text())
print('GOAL:', t['goal'])
for event in t['events']:
    a = event['action']
    args = {k: v for k, v in a['args'].items() if k not in ('content', 'evidence')}
    print('turn', event['turn'], a['tool'], json.dumps(args, ensure_ascii=False), event['status'])
    if event.get('error'):
        print('  preserved rejection:', event['error'])
print('MODEL DECISIONS:', len(t['model_calls']))
print('EXACT SOURCE QUOTES:', len(t['evidence']['ADR-001-ticket-context.md']))
PY
sed -n '1,30p' day-34-file-assistant/evidence/original/ADR-001-ticket-context.md
```

Сказать: «Модель сама читала main, MCP client, support agent, CRM fixtures и тесты. Поток get_ticket(T-101), user_id из тикета, затем get_user(U-001). В trace сохранён отказ записи из-за двух неверных цитат, затем модельное исправление аргументов и успешная запись. Техническая часть прошла, но качество исходного ADR осталось PARTIAL».

## 3:40–4:30 — честная редакционная проверка

```bash
sed -n '1,30p' day-34-file-assistant/evidence/reviewed/ADR-001-ticket-context-reviewed.md
sed -n '1,45p' day-34-file-assistant/evidence/editorial-changes.diff
```

Сказать: «Последний модельный вызов исправил evidence.quote, но не сам Markdown. Рецензент отдельно уточнил CLI prepare, всегда офлайн HTTP и retrieval через SQLite FTS5/BM25. Правки явно подписаны и показаны в diff. Исходный модельный файл не переписан; редакторская версия не выдаётся за модельную».

## 4:30–5:20 — replay, 65 тестов, SHA и приёмка

```bash
python3.13 day-34-file-assistant/verify_delivery.py
cat day-34-file-assistant/evidence/acceptance.json
```

Сказать: «Одна команда проверяет исходники, manifest и SHA, точный редакционный diff, сохранённые evidence, 65 offline-тестов и оба replay через исходный агентный цикл. Результаты и diff совпали, новых POST ноль. Проверка воспроизводит сохранённую работу; она не заменяет независимую смысловую оценку. В финальной приёмке отдельно видны original ADR PARTIAL и reviewed ADR PASS».

## 5:20–5:40 — итог

```bash
sed -n '1,22p' day-34-file-assistant/FINAL_REPORT.ru.md
```

Сказать: «Day 34 закрыт как Course Minimum PASS с документированной редакционной проверкой. Настоящая модель самостоятельно выполняет файловые операции в двух сценариях. Есть Markdown, diff, точные ссылки и повторное воспроизведение. OpenAI — десять POST, Groq — четыре, оценка OpenAI около девяти центов; billing неизвестен. Без новых генераций и расширения архитектуры перехожу к Day 35».

## Проверка перед записью

Запустить verifier заранее и убедиться в PASS. Увеличить шрифт Terminal, не выводить переменные окружения. При записи можно читать большие выводы с прокруткой; команды не требуют уникальных run ID и не перезаписывают исторические результаты. Длительность ориентировочная: не зачитывать JSON целиком. Это сценарий видео, а не утверждение, что видео уже записано.
