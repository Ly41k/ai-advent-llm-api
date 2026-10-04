> Исторический разбор. Для текущей v14 следуйте START_HERE.ru.md и FIX_DIAGNOSTIC_POLICY.ru.md.

> Историческое описание v12. Текущая версия — v13: START_HERE.ru.md и FIX_CRITERION_SCOPE.ru.md. Полный v12:8/10 +2/2; задание ещё не завершено.

# Исправление v12: доказательные ID вместо нового текста coverage

В полном v11 источники найдены, но coverage дал ложные отрицательные verdicts по01/03/05/06 и таблице04. На04/05/09 модель переписала/склеила excerpt: exact validator правильно отклонил строку, но полезный ответ не вышел. На10 команда journalctl названа observable result и правильно заблокирована local guard. Итог3/10 +2/2; все16 опубликованных цитат точны.

Новый coverage_proofs.py строит bounded literal sentence/line units только из выбранного кандидата. В одном criterion call модель возвращает reason/proof_ids/covered. JSON Schema enum и runtime validation исключают посторонние, duplicate, boolean ID, свободные claims/excerpts и лишние критерии. Программа назначает criterion ID и разрешает каждый proof ID в исходный текст и provenance; все proof strings — подстроки answer claim и source quote.

Для observation удалены identified shell commands и fragments действия. Это narrow eligibility rule: другие действия в prose могут быть ошибочно одобрены LLM, нужна ручная сверка. Prompt читает имена в коде, graph/table guards и lesson provenance; общий tool discovery не требует отдельного invoke каждого инструмента. Никакие expected_terms, expected_sources или authored reference answers в production не используются.

Негативное covered остаётся false. При malformed verdict одна bounded format retry относится к тому же ответу; он не пересобирается из-за ошибки копирования доказательства. После двух selection attempts неподтверждённый ответ отказан. Source identity и обязательные sources/quotes сохраняются. Index/models/corpus неизменны.

103 теста Дня24: прежние93 адаптированы к proof IDs,10 новых проверяют exact ownership, неизвестные/спliced/duplicate ID, отрицательные verdicts, command/action filtering, actual v11 sources09/10, empty enum, bounded format retry и отсутствие uncited context. Legacy excerpt fixture adapter находится только в fixture_proofs.py и импортируется исключительно тестовыми fixtures, не production. Эти fixtures не доказывают качество Qwen.

Полный v12 live report пока не получен. Следующий этап — evaluate_v12.json на всех10+2 и ручная проверка. Не обещаем10/10 по offline tests.
