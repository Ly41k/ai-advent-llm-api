// Same-origin RU/EN strings. No browser storage or conversation translation.
const entries = [
  ["page.title","Bublik — приватный AI-чат","Bublik — private AI chat"],
  ["brand.mark","Б","B"], ["brand.name","Бублик","Bublik"],
  ["login.title","Место для ваших мыслей.","A place for your thoughts."],
  ["login.description","Приватный чат с локальной Qwen. Диалоги сохраняются на вашем сервере.","Private chat with local Qwen. Conversations are saved on your server."],
  ["login.username","Имя пользователя","Username"], ["login.password","Пароль","Password"],
  ["login.submit","Войти","Sign in"], ["login.connecting","Подключаемся к серверу…","Connecting to the server…"],
  ["login.reconnect","Повторить подключение","Reconnect"],
  ["login.privacy","Учётную запись создаёт владелец сервера. Облачные LLM не используются.","The server owner creates your account. No cloud LLMs are used."],
  ["login.required","Войдите в свою учётную запись.","Sign in to your account."],
  ["login.invalid","Неверное имя пользователя или пароль.","Incorrect username or password."],
  ["login.changed","Сессия изменилась. Войдите снова.","Your session changed. Sign in again."],
  ["login.logged_out","Вы вышли из учётной записи.","You have signed out."],
  ["settings.ui","Язык интерфейса","Interface language"], ["settings.reply","Язык ответов","Reply language"],
  ["settings.ru","Русский","Russian"], ["settings.en","Английский","English"],
  ["settings.saved","Настройки языка сохранены.","Language settings saved."],
  ["settings.failed","Не удалось подтвердить сохранение настроек. Проверьте соединение и обновите страницу.","Could not confirm the settings were saved. Check your connection and reload."],
  ["chat.close_list","Закрыть список диалогов","Close conversation list"],
  ["chat.open_list","Открыть список диалогов","Open conversation list"],
  ["chat.list","Диалоги","Conversations"], ["chat.list_label","Список диалогов","Conversation list"],
  ["chat.new","+ Новый диалог","+ New conversation"], ["chat.yours","Ваши диалоги","Your conversations"],
  ["chat.refresh_list","Обновить список диалогов","Refresh conversation list"],
  ["chat.more","Ещё диалоги","More conversations"], ["chat.logout","Выйти","Sign out"],
  ["chat.title","Ваш приватный чат","Your private chat"], ["chat.refresh","Обновить диалог","Refresh conversation"],
  ["chat.history","История диалога","Conversation history"], ["chat.messages","Сообщения","Messages"],
  ["chat.older","Загрузить более ранние сообщения","Load earlier messages"],
  ["chat.empty_title","О чём поговорим?","What shall we talk about?"],
  ["chat.empty_text","Создайте диалог или откройте сохранённый. Полная история остаётся на сервере.","Create a conversation or open a saved one. The full history stays on the server."],
  ["chat.retry","Повторить генерацию последнего вопроса","Retry the last question"],
  ["chat.message","Сообщение","Message"], ["chat.placeholder","Напишите сообщение…","Write a message…"],
  ["chat.send","Отправить","Send"], ["chat.bytes","{count} / 16 384 байт","{count} / 16,384 bytes"],
  ["chat.caution","Qwen может ошибаться. Проверяйте важные ответы.","Qwen can make mistakes. Check important answers."],
  ["chat.you","Вы","You"], ["chat.sending","Отправляем запрос…","Sending request…"],
  ["chat.omitted","В контекст модели не вошло ранних завершённых ходов: {count}. Они сохранены в истории.","Earlier completed turns omitted from model context: {count}. They remain saved in history."],
  ["chat.partial","Ответ не завершён. Сохранённая часть остаётся в истории.","The reply did not finish. Its saved part remains in history."],
  ["chat.polling","Восстанавливаем ответ периодическими запросами…","Recovering the reply by polling…"],
  ["chat.offline","Соединение потеряно. Отправленные генерации могут продолжаться на сервере.","Connection lost. Submitted generations may continue on the server."],
  ["delivery.label","Доставка запроса","Request delivery"],
  ["delivery.notice","Подтверждение доставки не получено. Повтор использует тот же запрос и не создаёт дубликат.","Delivery has not been confirmed. Retrying uses the same request and does not create a duplicate."],
  ["delivery.retry","Повторить доставку","Retry delivery"],
  ["delivery.discard","Проверить историю и отменить повтор","Check history and stop retrying"],
  ["delivery.confirm","Запрос мог быть сохранён на сервере. Проверим историю. Отменить дальнейшие повторы доставки?","The request may have been saved on the server. We will check history. Stop further delivery retries?"],
  ["delivery.check_history","Проверьте историю перед отправкой нового сообщения.","Check history before sending a new message."],
  ["dialog.eyebrow","НОВЫЙ ДИАЛОГ","NEW CONVERSATION"], ["dialog.title","Дайте ему имя","Give it a name"],
  ["dialog.name","Название","Title"], ["dialog.default","Новый диалог","New conversation"],
  ["dialog.cancel","Отмена","Cancel"], ["dialog.create","Создать","Create"],
  ["model.checking","Проверяем модель…","Checking the model…"],
  ["model.ready","{model} · локальная модель · готова","{model} · local model · ready"],
  ["model.unavailable","Модель временно недоступна · история доступна","Model temporarily unavailable · history available"],
  ["model.check_failed","Не удалось проверить модель","Could not check the model"],
  ["memory.toggle","Искать в прошлых разговорах","Search past conversations"],
  ["memory.sources","Поиск в истории: {count} источников для контекста","History search: {count} context sources"],
  ["memory.empty","Подходящие фрагменты в контекст не вошли. Это не означает, что такого сообщения нет в полной истории.","No suitable fragments entered the context. This does not mean the full history has no such message."],
  ["memory.source_label","Исходное сообщение памяти","Original memory source"],
  ["memory.message","Сообщение №{sequence}","Message #{sequence}"],
  ["memory.conversation","Исходный разговор","Original conversation"], ["memory.anchor","Источник","Source"],
  ["memory.window","Показан фрагмент разговора вокруг источника. Полная переписка доступна в истории этого диалога.","Showing the conversation around the source. The full conversation is available in this chat's history."],
  ["status.accepted","Сохранено","Saved"], ["status.queued","В очереди","Queued"],
  ["status.running","Бублик отвечает…","Bublik is replying…"], ["status.completed","Ответ сохранён","Reply saved"],
  ["status.truncated","Ответ достиг ограничения длины","Reply reached the output limit"],
  ["status.failed","Генерация завершилась ошибкой","Generation failed"],
  ["status.interrupted","Генерация прервана","Generation interrupted"], ["status.unknown","Неизвестный статус","Unknown status"],
  ["error.general","Не удалось выполнить запрос.","Could not complete the request."],
  ["error.connection","Нет подтверждения от сервера. Проверьте соединение.","No confirmation from the server. Check your connection."],
  ["error.retry_after","Повторите через {seconds} с.","Retry in {seconds} s."],
  ["error.authentication_required","Сессия завершилась. Войдите снова.","Your session expired. Sign in again."],
  ["error.csrf_failed","Сессия изменилась. Обновите подключение и повторите действие.","Your session changed. Reconnect and try again."],
  ["error.rate_limit_exceeded","Достигнут лимит запросов.","Request limit reached."],
  ["error.user_queue_full","Слишком много ваших запросов в очереди.","You have too many queued requests."],
  ["error.global_queue_full","Очередь сервера заполнена.","The server queue is full."],
  ["error.stale_revision","Диалог изменился на другом устройстве. История обновлена; проверьте её перед отправкой.","The conversation changed on another device. History was refreshed; check it before sending."],
  ["error.chat_has_outstanding_generation","В этом диалоге уже готовится ответ. История обновлена.","A reply is already being generated in this conversation. History was refreshed."],
  ["error.context_budget_exceeded","Сообщение не помещается в контекст модели. Сократите его.","The message does not fit the model context. Shorten it."],
  ["error.invalid_message","Сообщение должно содержать текст и занимать не больше 16 384 байт.","The message must contain text and fit within 16,384 bytes."],
  ["error.model_unavailable","Модель недоступна. Сохранённую историю можно читать.","The model is unavailable. Saved history is readable."],
  ["error.inference_recovery_required","Генерация приостановлена до восстановления сервера владельцем.","Generation is paused until the server owner completes recovery."],
  ["error.storage_unavailable","Хранилище временно недоступно.","Storage is temporarily unavailable."],
  ["error.service_unavailable","Сервис временно недоступен.","The service is temporarily unavailable."],
  ["error.retry_not_allowed","Этот ответ нельзя повторить. Обновите историю.","This reply cannot be retried. Refresh history."],
  ["error.idempotency_conflict","Ключ запроса уже использован с другим содержимым. Обновите историю.","The request key was used with different content. Refresh history."],
  ["error.not_found","Диалог недоступен этой учётной записи.","This conversation is not available to this account."],
  ["error.preferences_changed","Настройки изменились на другом устройстве. Они обновлены; выберите язык снова.","Settings changed on another device. They were refreshed; select the language again."],
  ["error.unsupported_language","Поддерживаются только русский и английский.","Only Russian and English are supported."],
];
export const SUPPORTED_LANGUAGES = Object.freeze(["ru","en"]);
export const catalogs = Object.freeze(Object.fromEntries(SUPPORTED_LANGUAGES.map((lang,i)=>
  [lang,Object.freeze(Object.fromEntries(entries.map(([key,...values])=>[key,values[i]])))])));
let language = "ru";
export function setLanguage(value) {
  if (!SUPPORTED_LANGUAGES.includes(value)) throw new Error("unsupported_language");
  language=value;
}
export function locale() {return language==="ru"?"ru-RU":"en-US";}
export function languageForBrowser(values=[]) {
  for (const value of values) {const lang=value.toLowerCase().split("-")[0];if (SUPPORTED_LANGUAGES.includes(lang)) return lang;}
  return "ru";
}
export function t(key,values={}) {
  const template=catalogs[language][key];
  if (typeof template!=="string") throw new Error("unknown_translation_key");
  return template.replace(/\{([a-z_]+)\}/g,(_,name)=>String(values[name]??""));
}
export function errorMessage(code) {return catalogs[language]["error."+code] || t("error.general");}
export function statusLabel(code) {return catalogs[language]["status."+code] || t("status.unknown");}
export function translateStatic(root) {
  for (const node of root.querySelectorAll("[data-i18n]")) node.textContent=t(node.dataset.i18n);
  for (const attr of ["aria-label","placeholder"]) {
    for (const node of root.querySelectorAll(`[data-i18n-${attr}]`)) node.setAttribute(attr,t(node.getAttribute(`data-i18n-${attr}`)));
  }
}
