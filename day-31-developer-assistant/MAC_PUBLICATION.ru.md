# Проверка сохранённого human review на Mac

Основание: присланный `bundle-0003.json`;79/79 report SHA проверены. Все79 reports совпали с ранее проверенной публикацией; исходные76 live reports сохранены без изменения. Это проверка нового Mac артефакта, не предположение о выполнении команды.

| Проверка | Результат |
|---|---|
| Request | 629bcdc705604d68a43968d5469ac9ba |
| Result binding | 37d5205e0708b21247834cd8b6a285c31c07703c0609dc7a9801ffad58d28a4e |
| Human review SHA | 7ed6948e516e35d077888b5e8ee34b4c3e24590a6d1011ffc4cf41ecb6674174 |
| Reviewer | yuriy / human, явное решение пользователя |
| c1/c2 | supported / supported |
| Runtime validation | passed |
| answer_accepted | true |
| Raw/evidence/claims/anchors/fingerprints | совпали с принятыми исходными данными |
| Dispatch/terminal/reservation | 1 / 1 / 1 — прежний согласованный live |
| Новых Qwen calls при human publish/Stage8 | 0 |

При проверке использован неизменённый semantic envelope verifier с явно заданным доверенным human ID; bindings/содержимое не менялись. Синтетическое human approval не использовалось. Native audit/runner summary сохраняют исторические метки: это не изменение старых результатов задним числом. Текущее положительное решение находится в отдельном derived review/public result; Course Minimum Accepted — отдельное учебное решение.

Принимаемое ограничение RU1: защитная причина исключения прерванных/неуспешных запросов не объяснена явно. Пользователь подтвердил, что для Course Minimum это не блокер. Grounding двух claims подтверждён собственной точной цитатой, не полным документом.

В Stage8 заново не запускались Qwen, embeddings, индексы,32/83/276 suites или расширенная регрессия. Подготовлены только внешние файлы документации, проверка существующих данных и статическая проверка команд. Структурированный receipt находится в Stage8 package `evidence/mac-publication-check.json`.

Course Minimum Accepted; Research Stage7 paused/incomplete; документация Stage8 подготовлена, видео записано по сообщению пользователя. Начата подготовка размещения файлов для Git; commit/push не выполнялись. Исходный receipt ниже остаётся историческим.
