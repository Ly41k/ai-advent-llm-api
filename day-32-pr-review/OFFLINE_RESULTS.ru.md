# Day 32 — результаты offline-поставки

**PASS только для локальных контрактов и синтетической интеграции. Live acceptance не выполнена.**

| Проверка | Фактический результат |
|---|---|
| Среда | Linux, Python 3.12.14, SQLite FTS5 |
| unittest | **53 passed, 0 failures, 0 errors, 0 skipped** |
| Python | AST всех Python-файлов разобран; приложение также прошло py_compile во время разработки |
| YAML | Разобран локальным PyYAML BaseLoader; проверены events, Environment, permissions и отсутствие ключа в preflight/publish |
| Offline CLI / synthetic docs | `completed`, один заранее написанный mock-review |
| Offline CLI / реальные README Day 32 | `completed`, реальный FTS5 по документации пакета и синтетический PR/ответ |
| Внешние HTTP/API-вызовы | **0** |
| Реальные generation calls | **0** |
| Реальные ключи | Не использовались |
| GitHub writes / Actions runs | **0 / 0** |
| Mac Python 3.13 | Не проверен |
| Groq model/usage/качество | Не проверены настоящим запросом |
| Environment/branch policy | Не проверены на GitHub |

Логи: `verification/unittest.log`. Машинный итог: `verification/test-results.json`. Два набора sample-отчётов: `verification/offline-demo/` и `verification/base-docs-mock/`. В них `mode=offline_mock`, настоящие generation/network/GitHub calls равны нулю; synthetic observations учтены отдельно.

Обязательные сценарии покрыты: positive PR/files/hunks/RAG/validation/report; отсутствующие и недопустимые пути/строки; LEFT/delete и rename; context-only anchors; fake evidence; malformed/duplicate JSON/NaN; missing/binary/oversized/incomplete patch; synthetic secret assignments и JSON escaping; prompt-injection как данные без исполнения; fork/private/closed/wrong actor/branch; изменение SHA до и после генерации и перед публикацией; missing key; fake HTTP 429/500/timeout/transport error; incomplete/wrong-model/tool-call/missing-usage response; попытка второго generation call; forbidden GitHub mutations; bot comment update и защита human comments; неверный approval/ref/rerun; подмена отчёта.

На первом прогоне были найдены и исправлены две проблемы: тестовый разбор query page ошибочно совпадал с `per_page`; raw JSON escaping скрывал секретоподобное присваивание от plain-text фильтра. Проверка перенесена также на декодированные значения. Затем проверка реальной документации выявила недостаточный совместный budget для длинного README chunk и diff; chunking сокращён до 600 байт, добавлен scoped demo README, generic code keywords исключены из retrieval-запроса. Итоговый полный прогон прошёл.

Область доказательства ограничена. Подменённые HTTP-ответы не подтверждают работу аккаунта/квот/API/Actions. Проверка evidence подтверждает источник и строки, но не семантическую правильность инженерного вывода. YAML parsing — не запуск GitHub Actions и не серверный actionlint. SHA закреплённых Actions не проверялись удалённо на этом этапе.

Переход к следующему этапу: после отдельного разрешения — bootstrap из `day32-bootstrap`, merge доверенной реализации, настройка защищённого Environment, один live-тест из `day32-demo`. Полный сценарий и действия при ошибке — в README RU/EN. Оценка остатка: 45–90 минут активной работы плюс ожидание approval/merge.
