# Ручная проверка пользовательского v10 — 2026-10-03

Автоматически4/5, вручную подтверждены4 опубликованных ответа:01/05/07/10.09 отказал по форме/доказательству coverage при наличии полного source answer в selection. Все passages literal. Ответы перегружены, содержат RU/EN duplicates и обрезанные пример/таблицу/docstring, но основные прямые фрагменты отвечают на четыре вопроса. Это частичный прогон без отрицательных controls; задание ещё не закрыто.

Оригинал сохранён побайтно. В reviewed добавлены только ручные поля/summary/provenance, исходные model answers/metrics/decisions не изменены.

| Вопрос | Итог | Ручная сверка |
|---|---|---|
| positive-01 | answered | Полный смысл есть: UUID, только selected conversation_id в каждом LLM request и восстановление сообщений выбранной темы при запуске. Начало ответа needs a new cooling module — обрезанный/нерелевантный пример; ответ перегружен. Он не опровергает правильные прямые passages, но качество подачи требует улучшения. |
| positive-05 | answered | stdio_client → ClientSession.initialize → list_tools → вывод имён/описаний показаны в коде и документации. Механизм discovery объяснён. Повтор RU/EN и ping example лишние; исходный код в ответе стоит оформлять fenced block. Отдельный invoke add вопрос не требует. |
| positive-07 | answered | worker.py/independent worker, GitHub REST и сохранение snapshots в SQLite прямо присутствуют. Роли agent/worker сохранены. Есть повтор RU/EN и обрезанная server.py docstring; основной ответ подтверждён прямым intro/Components. |
| positive-09 | unknown | Итоговый отказ. Однако оба selection одинаковы и содержат полный direct answer:3MCP servers+registry, order of calls, compare disk report vs original summary, success only verified=true. Coverage возвращает question дважды и observation повторяет action; strict validator обоснованно не принимает такую форму. Отказ не засчитывается как содержательный ответ. |
| positive-10 | answered | Итоговые passages содержат VPS schedule/shared DB, systemctl/journalctl commands, stdout summary after each run и таблицу проверки двух snapshots/aggregate samples. В совокупности есть действия и наблюдаемая повторная сводка/снимки. Автоматический observation excerpt journalctl-command выбран ошибочно: он описывает действие, не результат. Обрезанная последняя строка таблицы и лишний heading ухудшают подачу; source text literal. |

Сверены24 опубликованных quotations, 48 candidate passages, 25 selected chunks и446 catalog fragments. Identity claim.text/quote, source/section/chunk_id, строки и source bindings согласованы. Все done_reason=stop; prompt tokens756–7223 при ctx16384.

## Ошибки аудита и следующий этап

09: две строки question вместо одной, а comparison action используется как observation. Не удалять duplicate с автоматическим approval и не подменять verdict вручную. Вместо общего массива требований — отдельный вызов на каждое требование с одним verdict без ID; ID назначает приложение. Негативная оценка остаётся негативной.

10: observation excerpt journalctl-command содержится внутри action excerpt. Требуется самостоятельная выдержка с ожидаемым результатом; вложенная/та же команда больше не может засчитываться как результат. Весь текущий source answer вручную достаточен за счёт intro про summaries after each run и таблицы двух snapshots, но этот конкретный model proof ошибочен.

Новая версия сохраняет exact extraction и уточняет coverage/подачу Python code. Релевантность и полнота остаются модельной/ручной оценкой. После применения исправления перейти к полному10+2, а не складывать четыре результата v10 с иными версиями. Проверить каждый из10 новых ответов и оба отрицательных controls.
