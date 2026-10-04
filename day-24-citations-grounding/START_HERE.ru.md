# Консольная версия для записи видео — v14

В корне существующего проекта:

```bash
unzip -o ~/Downloads/day24-console-demo-v14.zip -d .
source .venv/bin/activate
python day-24-citations-grounding/console_demo.py
```

Enter — следующий экран/страница. Скрипт показывает полный сохранённый реальный прогон ваших evaluate_again/threshold_check, sources/sections/chunk IDs, все53 цитаты, повторную проверку файлов, исходный coverage7/10 и записанную ручную проверку10/10. Новая генерация при просмотре не выполняется.

Для генерации через Ollama в кадре: `python day-24-citations-grounding/console_demo.py --live`. Новые результаты сохраняются отдельно, требуют новой ручной проверки. Основная RAG v14 не менялась. Инструкция и моменты для комментария: CONSOLE_VIDEO.ru.md. Тесты:116 основных+19 презентационных. Старые модели/индекс/папки предыдущих дней сохраняйте.

Ниже — информация о предшествующей поставке v14; имена старых архивов относятся к ней.

---

# День24 — итоговый архив v14

Задание подтверждено на полном пользовательском v14 diagnostic прогоне:10/10 содержательных ответов с источниками и цитатами после ручной проверки,53/53 цитаты exact,2/2 правильных отказа. Model coverage остаётся7/10; три negative judgments01/03/05 не исправлялись, а рассмотрены вручную. Проверка ассистентом не равна независимой человеческой оценке. Отчёт: reports/live/REVIEW_evaluate_v14.ru.md.

**Повторный запуск для завершения этого задания не требуется.** Итоговый архив содержит ту же программу v14 и добавляет original/reviewed live report, checklist и документацию. Программные файлы побайтно те же, что в day24-source-review-v14.zip; новая версия модели/индекса не нужна.

Для применения документации/результатов из терминала VSCode в корне существующего проекта:

```bash
unzip -o ~/Downloads/day24-completed-v14.zip -d .
```

Архив включает только полную папку Дня24, инструкцию и manifest. .env/.venv/knowledge.db/models/reports/check туда не входят. Сохраняйте их; папки Дней21–23 нужны для программы. Root README/source-revision раннего патча не включены.

Для самостоятельного повторения при необходимости:

```bash
source .venv/bin/activate
python day-24-citations-grounding/test_day24.py -v
python day-24-citations-grounding/main.py --coverage-policy diagnostic evaluate \
  --output day-24-citations-grounding/reports/check/evaluate_again.json
```

116 tests и OK;150 local tests суммарно с регрессиями. Model coverage diagnostic не является quality pass. Каждый новый report.initial assignment_complete=false до manual review, даже если sources/quotes10/10; результаты модели автоматически не изменяются. При повторном run нужно вновь проверить все10 по источникам.

Для strict default уберите --coverage-policy diagnostic: публикация тогда зависит от positive model coverage и false refusals возможны. Diagnostic сохраняет false coverage и manual_review_required, публикует только exact app-validated passages. Unknown при below0.50 и selector unknown сохраняется; invalid quotes/free synthesis блокируются; technical errors не маскируются. Полный пройденный workflow включает ручную оценку.

Original evaluate_v14_original.json сохранён побайтно. Reviewed evaluate_v14_reviewed.json добавляет только manual_review/manual_summary/provenance. Original summary.assignment_complete=false остаётся исходным; **manual_summary.assignment_complete=true** — итог после review. Model coverage7/10 и semantic_verifier_pass0 сохранены; extractive identity не является отдельным semantic LLM verdict.

Ответы остаются extractive на исходном языке, есть избыточность, дубли и cut passages. Нужные прямые passages покрывают вопросы; это не гарантия качества для всех будущих запросов. Подробности: VERIFICATION.ru.md, ASSIGNMENT_CHECKLIST.ru.md, reports/live/REVIEW_evaluate_v14.ru.md.
