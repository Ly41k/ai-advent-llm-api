# v0.4.1 — исправление API-path validation и диагностика

Mac v0.4.0: все 128 tests и offline smoke прошли; 40 docs / 380 chunks,
hybrid index verified. RU Qwen ответил корректно с точной цитатой. EN Documentation
вернул completed terminal response (871 input / 41 output tokens), но validator
отклонил его, Main не запускался. Отчёт честно failed и сохранён без изменений.
Все 40 Python digests совпали с выданным v0.4.0 архивом.

Воспроизведён дефект v0.4.0: API-путь в «The API prefix is /api/v1.» распознавался
как /api/v1. с точкой, которой нет в источнике PREFIX=/api/v1. Новый parser отделяет
точку обычного предложения, сохраняет literal inline code и остальные проверки.
Причина именно неуспешного Mac ответа пока не установлена: он не сохранён.

Фиксированные validation reasons в metrics различают JSON/schema/evidence/language/
identifier/truncation/Main-ID ошибки. Они не содержат ответ модели. Уже завершённый
вызов остаётся учтённым, rejected output не повторяется и не возвращается как claim.

Изменены generation.py, tests/test_pipeline.py (+3 regression methods), версия
__init__.py/pyproject.toml, инструкции. Полный suite 131. Prompt/schema, вопросы
проверки, retrieval, thresholds и acceptance не менялись. project/docs байт-в-байт
совпадает с v0.4.0: пересборка текущего verified hybrid index не требуется.

Следующий шаг: check_stage5.py --live с новым output v041.json. Успех требует
RU Documentation и EN Documentation/Main с двумя разными реальными contexts.
Stage 6 не начат до acceptance Stage 5.
