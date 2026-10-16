# v0.7.4 — полнота ответов и порядок парных запусков

Полная Mac серия v073: 20 пар, 40 ответов, 50 Qwen calls, 44 790 input /
3 638 output tokens, 0 technical failures/retries/unknown attempts.
55 source digests и все 50 model input/schema/budget digests проверены.
Неподтверждённых опубликованных фактов в разборе Codex не найдено; остаются
два self-reported partial и четыре неполных явных ответа про отдельные копии Qwen.
Human review ещё pending; это known regression, не held-out.

Retrieval на 44/405: FTS MRR .90, dense/vocabulary .95, hybrid/raw .95,
hit@5 10/10 и 2/2 empty negatives во всех вариантах. Selected acceptance passed;
uniform raw acceptance failed по MRR — сохранено без переписывания.

## Установка и запуск

Из корня repo с активным `.venv`:

```bash
unzip -o ~/Downloads/day31-stage7-v074.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v074_mac.sh
```

Ожидается 0.7.4. Полный архив дня 31; другие дни/root README не меняются.
**Индекс не пересобирать.** Все восемь project/docs и retrieval прежние;
текущий index 27519cd6caa346ac87a18639932506b5 остаётся свежим.
Новый freeze нужен из-за prompts/code/order protocol/catalog.

Helper выполняет native suite (ожидается 241 tests), index verify, zero-model
FTS/admission checks, сохраняет точный plan и новый freeze. Затем шесть пакетов:

| Тема RU/EN | Максимум Qwen calls |
|---|---:|
| Main, контроль прежнего исправления | 6 |
| Dense Project RAG vs личная память | 6 |
| Перефразировки и embedding | 4 |
| Сериализация и отдельные копии модели | 6 |
| Untracked content при explicit allowed paths | 4 |
| Несуществующие параметры, unknown controls | 4 |

Всего 12 вопросов, 24 observations, **до 30 последовательных Qwen calls**.
Реальных embedding calls — 0. Другие model clients по-прежнему выключены;
используется ранее выделенная Ollama session. Автоматического restart/replay нет.
При закрытом gate — прежняя explicit verified recovery/prepare/confirm процедура.

Изменены общие правила формулирования ответов для обоих режимов. `partial` по-прежнему
допустим и не переписывается приложением; улучшение смысла подтвердят новые ответы.
Baseline получает те же quotes/Git facts, модель/OPTIONS/бюджеты одинаковы.
Corpus и индекс те же. Порядок изменён отдельно и явно записан в plan/report;
не делать причинных или speed-выводов по сравнению с прежней серией.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v074.json
/tmp/day31-index-verify-mac-v074.json
/tmp/day31-quality-admission-mac-v074.json
/tmp/day31-quality-plan-mac-v074.json
/tmp/day31-quality-freeze-mac-v074.json
/tmp/day31-quality-main-mac-v074.json
/tmp/day31-quality-dense-mac-v074.json
/tmp/day31-quality-paraphrase-mac-v074.json
/tmp/day31-quality-serialized-mac-v074.json
/tmp/day31-quality-untracked-mac-v074.json
/tmp/day31-quality-unknown-mac-v074.json
```

При остановке — уже созданные отчёты и terminal error. Не запускать helper целиком
повторно: он защищает существующие outputs до первого шага. Успешные пакеты не
повторять. Technical failures сохраняются и останавливают следующий пакет.
Semantic partial/unknown сохраняются и требуют разбора, не означают transport failure.

Для следующего ещё не выполненного шага после устранения конкретной причины:

```bash
python day-31-developer-assistant/scripts/compare_single_multi.py run \
  --cases day-31-developer-assistant/evaluation/research_quality_regression_v074.json \
  --freeze /tmp/day31-quality-freeze-mac-v074.json \
  --case-id dense-private-branch-ru --case-id dense-private-branch-en \
  --repeats 1 --max-generation-calls 6 \
  --output /tmp/day31-quality-dense-mac-v074.json
```

Если пакет уже запускался и остановился, выбрать новое output имя, сохранив старый
failure. После uncertain inference сначала verified recovery; silent replay запрещён.

## Порядок и дальнейший план

Catalog position теперь задаёт S/M/M/S блоки; следующий repeat переворачивает порядок.
Он не сбрасывается при запуске отдельного пакета. Три repeats нельзя идеально
сбалансировать для одного вопроса (2:1); на 20 вопросах с чередующимися RU/EN
каждая языковая группа получает 15 Single-first и 15 Multi-first за три repeats.
Для конкретного held-out catalog распределение проверить в `plan` до запуска.

Здесь только один known-regression repeat. После targeted проверки нужны остальные
вопросы под v4, независимый held-out/human review, три paired repeats, end-to-end,
cold/warm и RAM/swap. Этап 7 открыт. Три repeats ещё не запускаются этим helper.
Исторические инструкции v073 — RESEARCH_MAC_V073.ru.md.
