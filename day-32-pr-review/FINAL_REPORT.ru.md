# Day 32 — итоговая приёмка

Дата: 2026-10-16. **Day 32 принят владельцем в статусе PARTIAL.**

| Область | Итог |
|---|---|
| Day 32 Course Minimum | PARTIAL — принят с сохранёнными ограничениями |
| Local technical integration | PASS |
| Local AI review quality | PARTIAL |
| GitHub Actions preflight | PASS |
| GitHub Actions live E2E | FAIL — две ошибки HTTP 403 |

Локальный результат имеет `execution_environment=local_mac`; он не является успешным GitHub Actions live E2E. Технический `completed` не подменяет ручную оценку качества.

## Неизменяемая привязка и история

- Repository: [Ly41k/ai-advent-llm-api](https://github.com/Ly41k/ai-advent-llm-api).
- Bootstrap [PR #1](https://github.com/Ly41k/ai-advent-llm-api/pull/1) merged; доверенный base/main/source: `c450c3fc4f643531889162c4acbb068abb9bf1c6`.
- Demo [PR #2](https://github.com/Ly41k/ai-advent-llm-api/pull/2) открыт, Draft. Head: `ae74ec45c288e7f0547f7fdf380a24edf9a848e8`.
- Единственное изменение demo — `day-32-pr-review/demo/percentage.py`, намеренный `return value / 0`. Файл не выполнялся, PR не merge и не закрыт.
- Первоначальный bootstrap workflow validation defect был исправлен до merge. История последующих неудачных попыток ниже сохраняется.

| Настоящий GitHub run | preflight | review | publish | Попыток Groq POST |
|---|---|---|---|---:|
| [38940777931](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38940777931) | success | skipped | skipped | 0 |
| [38945811433](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433) | success | failure: http_403 | skipped | 1 |
| [38952494436](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436) | success | failure: http_403 | skipped | 1 |

Это отдельные dispatch, оба live attempt=1; второй не был Re-run jobs. По artifacts обеих ошибок usage/request ID неизвестны, github_calls=4, retrieval_selected_chunks=3. `generation_calls=1` означает одну попытку POST, а не успешную генерацию. Ни retry, ни OpenAI fallback не выполнялись.

Оригинальные artifacts, копии которых сохранены в отдельном непубличном evidence package:

| Artifact | ID / ссылка | SHA256 оригинального ZIP |
|---|---|---|
| day32-preflight-38940777931-1 | [12063625798](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38940777931/artifacts/12063625798) | `27eb2618169cba86a43c4eb60250a7b85793d65990355d972a6a3e37cde435a3` |
| day32-review-38945811433-1 | [12067388422](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433/artifacts/12067388422) | `d0fffac59223fac687c0e41fe07aed7e632d535bf274ce089fe9f08f764d9be2` |
| day32-review-38952494436-1 | [12068454878](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436/artifacts/12068454878) | `93fd07d386e04bec90d5e9de03da6e9c33e3a70c12b41e002bdaa8a2c0bd26ec` |

GitHub retention ограничен: исходные artifacts могут истечь; локальные ZIP-копии сохраняют доказательства. Дополнительные preflight artifacts live-run: [12066290998](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433/artifacts/12066290998) и [12067859561](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436/artifacts/12067859561). Их metadata/ссылки сохранены; отдельные ZIP этих двух дополнительных preflight не входят в пакет.

## Настоящий локальный full review

Groq `openai/gpt-oss-120b`, Mac Python 3.13.3, curl 8.7.1. Один разрешённый POST, HTTP **200**, curl exit 0, без retry, redirects и fallback. Локальный helper остаётся внешним; исходники приложения и workflow не менялись.

- Usage: **649 input / 284 completion tokens**.
- HTTP request ID: `req_01m533sf0sev1r2mnq27rfh7t6`.
- Completion ID (`response.id`, поле request_id исходного адаптера): `chatcmpl-9bfc9e5b-ff81-43b1-b816-8c619cda2e3c`.
- Request body SHA256: `1e649afdab2d725d4597a615bfb47ec37ef03ad783322a3ce8b065e690a0cdc5`.
- Context digest: `23012115b65569b33653636cf7dae77e125cfadf964d838f8f7c6136f45b8944`.
- Input bound 3757 <=4000; max completion 2000, reasoning low, timeout 90 s.
- FTS5/BM25: 247 indexed chunks, 20 oversized chunks omitted, 3 selected documents, 2 changed lines. Это ограниченное retrieval, не анализ всего репозитория.
- Системный промпт, diff, документы и strict JSON Schema сформированы неизменённым `groq_adapter.request_body()`; байты сериализации совпали с подготовленным body. `mock_generation_outputs=0`.

Существующий валидатор принял один finding; rejected_findings=[] и omissions=[]. SHA integrity, Markdown и сохранённые findings повторно проверены offline. Схема/валидация исходного ответа прошли в локальном pipeline; при исходной итоговой проверке были доступны три отчёта. Затем владелец добавил сырой envelope и остальные оригиналы в приватный пакет на Mac; его содержимое в этой среде повторно не читалось.

## Ручная оценка качества

**Основной дефект обнаружен правильно:** [percentage.py:2](https://github.com/Ly41k/ai-advent-llm-api/blob/ae74ec45c288e7f0547f7fdf380a24edf9a848e8/day-32-pr-review/demo/percentage.py#L2) содержит `return value / 0`; для числового аргумента возникает ZeroDivisionError. Предложенное `/ 100` соответствует [доверенному контракту](https://github.com/Ly41k/ai-advent-llm-api/blob/c450c3fc4f643531889162c4acbb068abb9bf1c6/day-32-pr-review/demo/README.md#L3-L4).

Сохранённые ограничения:

1. Finding охватывает строки 1–2, включая дефектную строку 2. Диапазон допустим валидатором, но менее точен.
2. Evidence содержит только `F1H1R2`. Документы D1–D3 переданы в prompt, но document evidence ID в finding отсутствует; строгая доказательная связь с документом не продемонстрирована.
3. Дополнительный совет проверять zero input необоснован: нулевой input допустим, `0 / 100 = 0`. Основное исправление верно, дополнительная рекомендация не принимается.
4. `semantic_support_verified=false` в оригинальном summary оставлено без изменения. Настоящая ручная оценка зафиксирована этим отдельным отчётом; оригинальный ответ не редактировался ради PASS.

## Тесты и расходы

- Исходная offline suite: Mac Python 3.13.3, **53/53 PASS**, без модели; оригинальные log/summary сохранены. Имеющиеся файлы относятся к исходной Mac-проверке до bootstrap; повтор 53/53 после workflow fix подтверждён владельцем отдельно.
- Внешний local acceptance helper: **9/9 PASS на Mac** по предоставленному terminal transcript; HTTP/GitHub в этих тестах mock, настоящие FTS5/упаковка/валидация выполняются. Это не девять генераций.
- Actionlint 1.7.12: PASS после bootstrap fix; сохранён прежний результат, новый lint/запуск Actions при финализации не выполнялся.
- SQLite `ResourceWarning: unclosed database` сохранён как отдельное замечание; тесты при этом прошли. Исправление сейчас не внедрялось.

| Наблюдение | Input / completion | Расчётная list-price стоимость | Фактическое списание |
|---|---:|---:|---|
| Mac full review | 649 / 284 | $0.00026775 | Не подтверждено, actual_billed_usd=null |
| Отдельный Mac smoke-test, по сообщению владельца | 74 / 19 | $0.00002250 | Не подтверждено; исходный API response не передан |
| Две Actions попытки HTTP 403 | null / null | Неизвестно | Неизвестно |

Оценки используют сохранённый тарифный snapshot 2026-10-16: $0.15 input / $0.60 completion за 1M tokens. Это арифметика по usage, не invoice. Всего известных Day 32 POST-попыток — 4: две Actions failure, один Mac smoke-test и один Mac full review. Успешный full review не выдаётся за единственный вызов за всю историю дня. Free Plan подтверждён владельцем, но реальное списание $0 не заявляется. OpenAI API в Day 32 не использовался; ручной резерв около $5 для дней 32–35 не означает автоматического fallback.

## Причина HTTP 403 и backlog

Точная причина **не установлена**. Исходный urllib HTTPError handler отбросил provider body/headers. Успех полного прежнего payload на Mac исключает утверждение, что этот body вообще не может работать, но не изолирует причину отказа runner. Сетевой маршрут/IP, HTTP/TLS/User-Agent и права ключа/проекта остаются гипотезами; WAF, неверный ключ или необходимость платного плана не доказаны.

В [backlog после курса](BACKLOG_AFTER_COURSE.ru.md) перенесены безопасная диагностика 403, проверка полного payload внутри Actions, document evidence, необоснованные рекомендации и закрытие SQLite-соединений. Реализация сейчас не менялась. Новые реальные запросы требуют отдельного разрешения.

## Evidence и остановка

В отдельном приватном архиве сохранены оригинальные GitHub ZIP/отчёты, локальные отчёты и оригинальные Mac request.json/raw-response.json/POST_ATTEMPTED.json, Mac 53-test log/summary, transcript 9 тестов, ссылки и SHA256-манифест. При первой сборке трёх Mac-оригиналов не было; идентичный body был явно помечен как реконструкция. Владелец затем выполнил complete_on_mac.py без сети/генераций и подтвердил integrity PASS, secret_scan PASS_heuristic_no_matches, files_verified=49. Итоговый приватный архив: day32-finalization-with-mac-originals.zip; SHA256 `1e354d1522353de3fc6a57169115805602469ba755d7e8157873d821cf8602b8`. Этот последний hash и завершение переноса зафиксированы по результату владельца; сам итоговый ZIP здесь не передан и независимо не перепроверялся. Исходные модельные ответы не редактировались.

Для публичной поставки разрешены только README, этот итоговый отчёт, backlog и checksum metadata. Сырые request/response, модельные JSON/Markdown artifacts и приватный evidence package не включаются в GitHub без отдельного разрешения.

`DAY32_LIVE_ENABLED=false` сохранён; последнее подтверждение — успешная повторная проверка helper при локальной приёмке и сообщение владельца. На финализации флаг не включался. PR #2 открыт Draft, без merge/закрытия. При подготовке Stage 5 — ноль новых Groq/OpenAI-вызовов, dispatch, approvals или GitHub writes. Дни 1–31 и workflow не изменены. **STOP.**
