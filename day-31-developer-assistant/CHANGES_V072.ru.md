# v0.7.2 — исправление false context-budget rejection

v071 batch B остановился до Multi chat. Legacy estimate 8234 против 8192;
полный content 6315 bytes, outer transport overhead 127. Новый Byte-BPE estimate
content+256+1024+512=8107, без изменения prompts/options/evidence/model/retrieval.
Один счётчик для Single/Multi, подробная fixed numeric диагностика до admission,
real overflow по-прежнему блокируется до lease checkpoint/dispatch.

Шесть новых checks, exact public-input fixture; старый stopped report retained.
Новый budget policy входит в freeze. Новая regression-phase copy сохраняет все
question/rubric values, но не выдаётся за independent held-out. Старые вопросы
и v071 measurements остаются неизменны. Первый Mac smoke — RU/EN assistant facts,
max4 calls, затем отдельная полная серия при стабильном technical status.
Команды: RESEARCH_MAC.ru.md. Stage7 semantic/end-to-end/resources остаются open.

Локально 122/122 checks passed; source SHA неизменны. Native Mac 233 tests и
real four-call regression pending. Prompts/model/options/corpus byte-identical.
