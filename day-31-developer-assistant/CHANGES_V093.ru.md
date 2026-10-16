# v093 / 0.7.23 — проверка каждого пункта и повторов, один bundle

## Полная known regression v092

22 вопроса, 44 ответа Single/Multi, один paired repeat, 54 known calls:
50491 input / 4033 output tokens, 0 technical failures/retries/unknown inference/
embeddings. Отдельный production RU Doc control: ещё 1 call, 1131/98 tokens.
Итого 55 calls, 51622/4131 tokens. Native v092:262 tests passed,59 source SHA;
CURRENT44docs/405chunks прежний. Это не held-out/E2E/resource acceptance.

Untracked core корректен4/4. RU Multi добавил c2 «Нет упоминания о чтении
untracked файлов» с e3 из Day18 VPS README. Молчание посторонней цитаты не
доказывает политику дня31 или общее отсутствие сведений: e1/e2 прямо описывают
untracked. Paraphrase EN Multi повторил no-cloud source-binding gap: cloud clause
находится в e2, опубликованный c2 ссылается только на e1. Остались повторы смысла
в RU Multi assistant/language/uncertain и расширенные rubric omissions.
Прямую правильность и более широкую полноту считаем отдельно. EN language
retain-original-text семантически покрывает отсутствие перевода, без требования
дословно повторять отрицание. Dense детали частично пересекаются по смыслу;
их literal omissions не превращают четыре правильных прямых ответа в неверные.

51 raw reports, 2 original bundles, 12 отдельные reviews и exact55 input fixture
сохранены в reports/mac-v092. Никакие native ответы/рубрики не переписаны.

## Ограниченное изменение

Shared SOURCE_RULES: одинаковый факт нескольких цитат объединять в один claim;
сохранять полное релевантное положение, списки входов/прав, технологию, пределы,
область и обе стороны сравнения; перед JSON проверять каждую часть по выбранным
IDs. Молчание цитаты не доказательство. Без неподдержанного и повторов смысла.
Это инструкции модели, не новый semantic verifier. Улучшение ещё не доказано.

Первые две support/language строки и финальное status правило точны как в v092.
Prompt project-answers-v17; benchmark Single snapshot-single-v18. RU1099bytes,
EN794bytes; оба короче v092. Runtime AST generation/baseline изменён только
в prompt/version assignments. Schema source-prefix-v6, options8192/1024/temp0/
seed31, text/name guards, Router, corpus/retrieval, Main ID-only, budget/lease
прежние. Нет auto repair/citation append/status promotion/model retry/cloud.
Нет test IDs/paths/золотых ответов в production rules. pyproject version согласован.

## Один файл результатов

run_v093_mac.sh после checks и ОДНОГО positive RU untracked Doc call cap1 создаёт
/tmp/day31-stage7-mac-v093-bundle.json с семью оригинальными JSON и SHA-256.
Continue helpers создают /tmp/day31-paired-<packet>-mac-v093-bundle.json с четырьмя.
Отдельные raw files сохраняются. При сбое после начала checks упаковка включает
доступные reports и missing_files; исходный ненулевой exit code сохраняется.
Нет автоматического следующего packet/replay. Если report/bundle уже существует,
helper останавливается до dispatch. Bundler rejects symlinks/duplicate paths и
не перезаписывает файлы. Packaging itself generation0/embedding0.

## Verification

88 affected local tests passed; model transport synthetic. Native262pending.
297 historical/native input budgets max8173/8192, evidence not truncated.
17 shell/source/zero-model CLI checks +7 real bundle/AST invariant checks passed.
44 historical frames schema-valid,43accepted/1mixed-script rejection — compatibility,
не semantic PASS. Initial offline dependency-path/test-version mismatch report
retained as attempt1; исправлены local test setup/version expectations. Model/schema
behavior не ослаблялся ради PASS. Full native MCP suite требует Mac/Python3.13.

Следующий шаг: one positive RU untracked Doc control, cap1, fresh version freeze.
После review negative guard и парные targeted cases. CURRENT/bge-m3 НЕ rebuild.
Remaining stage7: semantic quality, final-version known regression и3paired repeats,
independent heldout/human review, E2E/actual changed-files Chain, controlled native
cold/warm/tokens/RAM/swap, research decision. Этап7 OPEN. Этап8 только после
completion notice и согласования времени с Юрием.
