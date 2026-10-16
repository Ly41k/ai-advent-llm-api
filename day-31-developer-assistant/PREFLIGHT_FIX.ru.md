# 0.1.1 — диагностика отключения day30

На Mac пользователь подтвердил настоящий MCP branch=`main` на ревизии
`f5cce79933a8535eda5b8d218e79a04aee88d029` и 34/34 tests за 11.855 s для 0.1.0.
Отдельный doctor вернул `day30_isolation_unverified`. Конкретная неуспешная
проверка не была видна в прежнем output; работающий day30 этим не доказан.

В 0.1.1:

- Process table использует отдельный `comm` для имени executable. Arguments
  проверяются только у подходящих launchers. `ps` display не разбирается как
  shell source: кавычки и апострофы не обязаны быть парными.
- Doctor выполняет и показывает отдельные probes для processes, launchd и ports.
  Даже при неуспехе одного шага остальные получают явный результат.
- Diagnostic содержит fixed reason и numeric returncode; private command lines,
  process args и stderr не печатаются.
- Unknown process/launchd state продолжает блокировать проверку. Условие
  отсутствующего launchd job не расширено без фактического Mac output.
- Добавлены 4 regression tests; Linux suite теперь 38/38. Mac-проверка новой
  версии ещё не выполнена. Исторический report 0.1.0 не перезаписывается.

Распаковать patch archive в корень репозитория с заменой совпадающих файлов.
Зависимости прежние; новую venv или переустановку пакетов создавать не нужно.

```bash
python day-31-developer-assistant/main.py doctor
```

При ошибке смотри `probes`:

| Reason/status | Значение |
|---|---|
| processes: unverified | Не удалось проверить process table/arguments |
| launchd_print_unrecognized | Неподдержанный ответ launchctl; returncode покажет, что уточнять |
| launchd_autostart_not_disabled | Job выгружен, но установленный LaunchAgent ещё не disabled |
| launchd: active | Job всё ещё загружен |
| loopback_port_8000: active | На API-порту найден listener |

Проверка idle Ollama по-прежнему не выполняется, model calls отсутствуют.
Для полного повторного отчёта используй новый путь, чтобы не затереть первый:

```bash
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage12.py \
  --output /tmp/day31-stage12-mac-v011.json
```
