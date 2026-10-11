// Private browser client. No credentials, drafts or history in browser storage.
const API = "/api/v1";
const TERMINAL = new Set(["completed", "truncated", "failed", "interrupted"]);
const LABELS = {accepted:"Сохранено", queued:"В очереди", running:"Бублик отвечает…",
  completed:"Ответ сохранён", truncated:"Ответ достиг ограничения длины",
  failed:"Генерация завершилась ошибкой", interrupted:"Генерация прервана"};
const ERRORS = {
  authentication_required:"Сессия завершилась. Войдите снова.",
  csrf_failed:"Сессия изменилась. Обновите подключение и повторите действие.",
  rate_limit_exceeded:"Достигнут лимит запросов.",
  user_queue_full:"Слишком много ваших запросов в очереди.",
  global_queue_full:"Очередь сервера заполнена.",
  stale_revision:"Диалог изменился на другом устройстве. История обновлена; проверьте её перед отправкой.",
  chat_has_outstanding_generation:"В этом диалоге уже готовится ответ. История обновлена.",
  context_budget_exceeded:"Сообщение не помещается в контекст модели. Сократите его.",
  invalid_message:"Сообщение должно содержать текст и занимать не больше 16 384 байт.",
  model_unavailable:"Модель недоступна. Сохранённую историю можно читать.",
  inference_recovery_required:"Генерация приостановлена до восстановления сервера владельцем.",
  storage_unavailable:"Хранилище временно недоступно.",
  service_unavailable:"Сервис временно недоступен.",
  retry_not_allowed:"Этот ответ нельзя повторить. Обновите историю.",
  idempotency_conflict:"Ключ запроса уже использован с другим содержимым. Обновите историю.",
  not_found:"Диалог недоступен этой учётной записи.",
};

export function messageBytes(value) { return new TextEncoder().encode(value).length; }
export function mergeMessages(existing, incoming) {
  const rows = new Map(existing.map(row => [row.id, row]));
  for (const row of incoming) rows.set(row.id, row);
  return [...rows.values()].sort((a,b) => a.sequence-b.sequence);
}
export function newerSnapshot(previous, incoming) {
  return !previous || (previous.id === incoming.id && incoming.stream_revision >= previous.stream_revision);
}
export class APIError extends Error {
  constructor(status, code, retryAfter=0) {
    super(ERRORS[code] || "Не удалось выполнить запрос.");
    this.status=status; this.code=code; this.retryAfter=retryAfter;
  }
}

if (typeof document !== "undefined") {
  const $ = id => document.getElementById(id);
  const state = {session:null, csrf:"", view:0, chat:null, messages:[], chats:[], cursor:null,
    before:null, loading:false, mutating:false, pending:null, watcher:null,
    ready:false, background:false, authBusy:false, cooldown:0};
  const status = value => { $("app-status").textContent=value; };
  const atBottom = () => $("message-scroll").scrollHeight-$("message-scroll").scrollTop-$("message-scroll").clientHeight<100;
  const scrollBottom = () => { $("message-scroll").scrollTop=$("message-scroll").scrollHeight; };
  const safeId = id => typeof id === "string" && /^[a-f0-9]{32}$/.test(id);

  async function api(path, {method="GET", body, key, quiet=false}={}) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(),20000);
    const headers = {};
    if (method !== "GET") {
      headers["Content-Type"]="application/json";
      headers["X-CSRF-Token"]=state.csrf;
      if (key) headers["Idempotency-Key"]=key;
    }
    try {
      const response = await fetch(API+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),
        credentials:"same-origin",cache:"no-store",redirect:"error",signal:controller.signal});
      const data = await response.json();
      if (!response.ok) {
        const code = data.error?.code || "unknown_error";
        const delay = Math.min(3600,Math.max(0,Number(response.headers.get("Retry-After")) || 0));
        if (response.status === 429) state.cooldown=Date.now()+Math.max(5,delay)*1000;
        if (response.status === 401 && !quiet && state.session) clearPrivate(ERRORS.authentication_required);
        throw new APIError(response.status,code,delay);
      }
      return data;
    } finally { clearTimeout(deadline); }
  }
  function errorText(error) {
    if (error instanceof APIError) return error.message+(error.retryAfter?` Повторите через ${error.retryAfter} с.`:"");
    return "Нет подтверждения от сервера. Проверьте соединение.";
  }
  function stopWatch() {
    if (state.watcher) {
      state.watcher.stopped=true;
      state.watcher.source?.close();
      clearTimeout(state.watcher.timer);
      state.watcher=null;
    }
  }
  function clearPrivate(message="") {
    stopWatch(); state.view++;
    Object.assign(state,{session:null,csrf:"",chat:null,messages:[],chats:[],cursor:null,
      before:null,pending:null,ready:false,loading:false});
    $("messages").replaceChildren(); $("chat-list").replaceChildren();
    $("message-input").value=""; $("password").value=""; $("account-name").textContent="";
    $("chat-title").textContent="Ваш приватный чат"; $("generation-info").textContent="";
    $("model-status").textContent="Проверяем модель…"; $("new-title").value="Новый диалог";
    $("create-dialog").close(); $("workspace").hidden=true; $("login-screen").hidden=false;
    $("login-status").textContent=message; $("connect-button").hidden=false;
    $("login-button").disabled=true; status(""); drawer(false); controls();
  }
  function controls() {
    const bytes=messageBytes($("message-input").value);
    $("message-size").textContent=`${bytes.toLocaleString("ru-RU")} / 16 384 байт`;
    const busy = state.messages.some(m=>m.role==="assistant" && !TERMINAL.has(m.status));
    $("message-input").disabled=!state.chat || state.loading || state.mutating || Boolean(state.pending);
    $("send-button").disabled=!state.chat || !state.ready || busy || state.loading || state.mutating || Boolean(state.pending)
      || !$("message-input").value.trim() || bytes>16384 || Date.now()<state.cooldown;
    $("new-chat").disabled=state.mutating || Boolean(state.pending);
    $("delivery-notice").hidden=!state.pending || state.mutating;
    $("replay-request").disabled=state.mutating || Date.now()<state.cooldown;
    const last=state.messages.at(-1);
    $("retry-generation").hidden=!(last?.role==="assistant" && ["truncated","failed","interrupted"].includes(last.status));
    $("retry-generation").disabled=!state.ready || state.mutating || Boolean(state.pending) || state.loading || Date.now()<state.cooldown;
    $("older-messages").hidden=state.before===null;
    $("older-messages").disabled=state.loading;
  }
  function drawer(open) {
    $("workspace").classList.toggle("drawer-open",open);
    $("drawer-backdrop").hidden=!open; $("menu-button").setAttribute("aria-expanded",String(open));
    if (open) $("new-chat").focus();
  }
  function renderChats() {
    $("chat-list").replaceChildren();
    for (const chat of state.chats) {
      const button=document.createElement("button"); button.type="button"; button.className="chat-item";
      if (chat.id===state.chat?.id) button.setAttribute("aria-current","page");
      const title=document.createElement("span"); title.textContent=chat.title;
      const date=document.createElement("small"); date.textContent=new Date(chat.created_at).toLocaleDateString("ru-RU");
      button.append(title,date); button.addEventListener("click",()=>openChat(chat.id).catch(e=>status(errorText(e))));
      $("chat-list").append(button);
    }
    $("more-chats").hidden=!state.cursor;
  }
  async function loadChats(more=false) {
    const owner=state.session?.id;
    if (!owner) return;
    const cursor=more && state.cursor?`&cursor=${encodeURIComponent(state.cursor)}`:"";
    const data=await api("/chats?limit=50"+cursor);
    if (state.session?.id!==owner) return;
    state.chats=more?[...state.chats,...data.items]:data.items; state.cursor=data.next_cursor; renderChats();
  }
  function messageNode(message) {
    const node=document.createElement("article"); node.className="message "+message.role;
    node.dataset.messageId=message.id; node.dataset.state=message.status;
    const label=document.createElement("span"); label.className="message-label";
    label.textContent=message.role==="user"?"Вы":"Бублик";
    const text=document.createElement("pre"); text.className="message-text"; text.textContent=message.content;
    const info=document.createElement("div"); info.className="message-state";
    info.textContent=message.role==="assistant"?(LABELS[message.status] || "Неизвестный статус"):"";
    node.append(label,text,info); return node;
  }
  function renderHistory() {
    $("messages").replaceChildren(...state.messages.map(messageNode));
    $("empty-state").hidden=state.messages.length>0;
    controls();
  }
  async function openChat(id) {
    if (!safeId(id) || !state.session) return;
    stopWatch(); const view=++state.view; state.loading=true; state.chat=null;
    state.messages=[]; state.before=null; renderHistory(); controls(); drawer(false);
    try {
      const page=await api(`/chats/${id}/messages?latest=true&limit=50`);
      const chat=await api("/chats/"+id);
      if (view!==state.view || !state.session) return;
      state.chat=chat; state.messages=page.items; state.before=page.next_before_sequence;
      $("chat-title").textContent=chat.title; $("generation-info").textContent="";
      history.replaceState(null,"",`#chat=${id}`); renderChats(); renderHistory(); scrollBottom();
      watchOutstanding();
    } finally { if (view===state.view) {state.loading=false; controls();} }
  }
  async function refreshChat(force=false) {
    if (!state.chat || state.loading || !state.session) return;
    const id=state.chat.id, view=state.view;
    const chat=await api("/chats/"+id);
    if (view!==state.view) return;
    if (force || chat.revision!==state.chat.revision) {
      const page=await api(`/chats/${id}/messages?latest=true&limit=50`);
      if (view!==state.view) return;
      const bottom=atBottom(); state.messages=mergeMessages(state.messages,page.items); state.chat=chat;
      renderHistory(); if (bottom) scrollBottom(); watchOutstanding();
    } else state.chat=chat;
    $("chat-title").textContent=chat.title;
  }
  async function older() {
    if (!state.chat || state.before===null || state.loading) return;
    const view=state.view, height=$("message-scroll").scrollHeight, top=$("message-scroll").scrollTop;
    state.loading=true; controls();
    try {
      const page=await api(`/chats/${state.chat.id}/messages?before_sequence=${state.before}&limit=50`);
      if (view!==state.view) return;
      state.messages=mergeMessages(state.messages,page.items); state.before=page.next_before_sequence;
      renderHistory(); $("message-scroll").scrollTop=top+$("message-scroll").scrollHeight-height;
    } finally { if (view===state.view) {state.loading=false; controls();} }
  }
  function watchOutstanding() {
    const row=state.messages.find(m=>m.role==="assistant" && !TERMINAL.has(m.status));
    if (row?.generation_id && state.watcher?.id!==row.generation_id) watch(row.generation_id);
  }
  function snapshot(watcher,data) {
    if (watcher.stopped || watcher!==state.watcher || data.chat_id!==state.chat?.id
        || data.id!==watcher.id || !newerSnapshot(watcher.last,data)) return;
    watcher.last=data; const bottom=atBottom();
    const row={...data.assistant,generation_id:data.id,error_code:data.error_code};
    state.messages=mergeMessages(state.messages,[row]);
    let node=[...$("messages").children].find(n=>n.dataset.messageId===row.id);
    if (node) node.replaceWith(messageNode(row)); else $("messages").append(messageNode(row));
    $("empty-state").hidden=true;
    const omitted=data.context?.omitted_turns || 0;
    $("generation-info").textContent=(LABELS[data.status] || "")+(omitted?` · В контекст модели не вошло ранних завершённых ходов: ${omitted}. Они сохранены в истории.`:"");
    if (data.error_code) status(ERRORS[data.error_code] || "Ответ не завершён. Сохранённая часть остаётся в истории.");
    if (bottom) scrollBottom(); controls();
    if (TERMINAL.has(data.status)) {
      stopWatch(); state.loading=true; controls();
      const view=state.view, chat=state.chat.id;
      api("/chats/"+chat).then(value=>{if (view===state.view) state.chat=value;})
        .catch(e=>status(errorText(e)))
        .finally(()=>{if (view===state.view) {state.loading=false; controls();}});
    }
  }
  function watch(id) {
    stopWatch(); if (document.hidden || !state.session || !safeId(id)) return;
    const watcher={id,stopped:false,last:null,source:null,timer:null}; state.watcher=watcher;
    const poll=async () => {
      if (watcher.stopped) return;
      try { snapshot(watcher,await api("/generations/"+id)); }
      catch (e) { if (!watcher.stopped) status(errorText(e)); }
      if (!watcher.stopped) watcher.timer=setTimeout(poll,Math.max(5000,state.cooldown-Date.now()));
    };
    const fallback=() => {
      if (watcher.stopped || !watcher.source) return;
      watcher.source.close(); watcher.source=null;
      $("generation-info").textContent="Восстанавливаем ответ периодическими запросами…";
      watcher.timer=setTimeout(poll,Math.max(1000,state.cooldown-Date.now()));
    };
    if (typeof EventSource === "undefined") {poll(); return;}
    watcher.source=new EventSource(API+"/generations/"+id+"/events");
    watcher.source.addEventListener("snapshot",event=>{
      try {snapshot(watcher,JSON.parse(event.data));} catch {fallback();}
    });
    watcher.source.addEventListener("reconnect",fallback);
    watcher.source.addEventListener("error",event=>{
      let code=null; try {code=JSON.parse(event.data).error?.code;} catch { /* Network error has no body. */ }
      if (code==="authentication_required") clearPrivate(ERRORS.authentication_required); else fallback();
    });
  }
  async function ready() {
    const owner=state.session?.id; if (!owner) return;
    try {
      const data=await api("/health/ready");
      if (state.session?.id!==owner) return;
      state.ready=data.status==="ready";
      $("model-status").textContent=`${data.profile.model} · локальная модель · готова`;
    } catch (e) {
      if (state.session?.id!==owner) return;
      state.ready=false; $("model-status").textContent=e instanceof APIError && e.status===503
        ?"Модель временно недоступна · история доступна":"Не удалось проверить модель";
    }
    controls();
  }
  async function bootstrap() {
    if (state.authBusy) return;
    state.authBusy=true; $("login-button").disabled=true;
    try {
      const data=await api("/auth/session",{quiet:true});
      if (state.session && data.user?.id!==state.session.id) clearPrivate("Сессия изменилась. Войдите снова.");
      state.csrf=data.csrf_token;
      if (data.user) await signedIn(data.user);
      else {state.session=null; $("login-status").textContent="Войдите в свою учётную запись."; $("connect-button").hidden=true;}
    } catch (e) { $("login-status").textContent=errorText(e); $("connect-button").hidden=false; }
    finally {state.authBusy=false; $("login-button").disabled=!state.csrf;}
  }
  async function signedIn(user) {
    state.session=user; $("account-name").textContent=user.username;
    $("login-screen").hidden=true; $("workspace").hidden=false; $("password").value="";
    await loadChats();
    const requested=location.hash.match(/^#chat=([a-f0-9]{32})$/)?.[1];
    if (!state.chat && requested) {
      try {await openChat(requested);} catch(e) {status(errorText(e)); history.replaceState(null,"",location.pathname);}
    }
    await ready();
  }
  async function login(event) {
    event.preventDefault(); if (state.authBusy || !state.csrf) return;
    state.authBusy=true; $("login-button").disabled=true;
    try {
      const data=await api("/auth/login",{method:"POST",body:{username:$("username").value,password:$("password").value},quiet:true});
      state.csrf=data.csrf_token; await signedIn(data.user);
    } catch (e) { $("login-status").textContent=e instanceof APIError && e.status===401?"Неверное имя пользователя или пароль.":errorText(e); }
    finally {$("password").value=""; state.authBusy=false; $("login-button").disabled=!state.csrf;}
  }
  async function deliver() {
    const operation=state.pending; if (!operation || state.mutating || !state.session) return;
    state.mutating=true; controls(); status("Отправляем запрос…");
    try {
      const receipt=await api(operation.path,{method:"POST",body:operation.body,key:operation.key});
      if (state.pending!==operation || !state.session) return;
      state.pending=null; $("message-input").value=""; status("");
      await loadChats(); await openChat(receipt.chat_id);
    } catch (e) {
      if (!state.session) return;
      const definite=e instanceof APIError && (e.status===403 || e.status===404 || e.status===409 || e.status===413 || e.status===415 || e.status===422 || e.status===429
        || e.code==="model_unavailable" || e.code==="global_queue_full" || e.code==="inference_recovery_required");
      if (definite) state.pending=null;
      status(errorText(e));
      if (e instanceof APIError && ["stale_revision","chat_has_outstanding_generation","retry_not_allowed"].includes(e.code)) {
        await refreshChat(true).catch(()=>{});
      }
      if (e instanceof APIError && e.status===403) await bootstrap();
    } finally {state.mutating=false; controls();}
  }
  function startOperation(path,body,kind) {
    if (state.pending || state.mutating || !state.session) return;
    state.pending={path,body,key:crypto.randomUUID(),kind}; deliver();
  }
  $("login-form").addEventListener("submit",login);
  $("connect-button").addEventListener("click",bootstrap);
  $("logout").addEventListener("click",async()=>{
    if (state.authBusy) return;
    state.authBusy=true;
    try { await api("/auth/logout",{method:"POST",body:{}}); clearPrivate("Вы вышли из учётной записи."); }
    catch (e) {status(errorText(e));}
    finally {state.authBusy=false; if (!state.session) bootstrap();}
  });
  $("new-chat").addEventListener("click",()=>{ $("new-title").value="Новый диалог"; $("create-dialog").showModal(); });
  $("cancel-create").addEventListener("click",()=>$("create-dialog").close());
  $("create-form").addEventListener("submit",event=>{
    event.preventDefault(); const title=$("new-title").value.trim(); if (!title) return;
    $("create-dialog").close(); startOperation("/chats",{title},"create");
  });
  $("composer").addEventListener("submit",event=>{
    event.preventDefault(); if ($("send-button").disabled) return;
    startOperation(`/chats/${state.chat.id}/messages`,{content:$("message-input").value,expected_revision:state.chat.revision},"send");
  });
  $("message-input").addEventListener("input",controls);
  $("message-input").addEventListener("keydown",event=>{
    if (event.key==="Enter" && !event.shiftKey && !event.isComposing && matchMedia("(pointer:fine)").matches) {
      event.preventDefault(); $("composer").requestSubmit();
    }
  });
  $("retry-generation").addEventListener("click",()=>{
    const user=[...state.messages].reverse().find(m=>m.role==="user"); if (!user) return;
    startOperation(`/messages/${user.id}/retry`,{expected_revision:state.chat.revision},"retry");
  });
  $("replay-request").addEventListener("click",deliver);
  $("discard-request").addEventListener("click",async()=>{
    if (!confirm("Запрос мог быть сохранён на сервере. Проверим историю. Отменить дальнейшие повторы доставки?")) return;
    try {
      if (state.chat) await refreshChat(true); await loadChats();
      state.pending=null; $("message-input").value=""; status("Проверьте историю перед отправкой нового сообщения."); controls();
    } catch(e) {status(errorText(e));}
  });
  $("refresh-chats").addEventListener("click",()=>loadChats().catch(e=>status(errorText(e))));
  $("more-chats").addEventListener("click",()=>loadChats(true).catch(e=>status(errorText(e))));
  $("refresh-chat").addEventListener("click",()=>Promise.all([refreshChat(true),ready()]).catch(e=>status(errorText(e))));
  $("older-messages").addEventListener("click",()=>older().catch(e=>status(errorText(e))));
  $("menu-button").addEventListener("click",()=>drawer(!$("workspace").classList.contains("drawer-open")));
  $("drawer-backdrop").addEventListener("click",()=>{drawer(false); $("menu-button").focus();});
  document.addEventListener("keydown",event=>{if (event.key==="Escape") drawer(false);});
  addEventListener("hashchange",()=>{
    const id=location.hash.match(/^#chat=([a-f0-9]{32})$/)?.[1];
    if (id) openChat(id).catch(e=>status(errorText(e)));
  });
  document.addEventListener("visibilitychange",()=>{
    if (document.hidden) stopWatch(); else if (state.session) bootstrap().then(()=>refreshChat(true)).catch(e=>status(errorText(e)));
  });
  addEventListener("online",()=>{if (state.session) refreshChat(true).then(ready).catch(e=>status(errorText(e))); else bootstrap();});
  addEventListener("offline",()=>status("Соединение потеряно. Отправленные генерации могут продолжаться на сервере."));
  addEventListener("beforeunload",event=>{
    if (state.pending || $("message-input").value.trim()) {event.preventDefault(); event.returnValue="";}
  });
  addEventListener("pagehide",()=>{
    stopWatch(); $("messages").replaceChildren(); $("chat-list").replaceChildren();
    $("message-input").value=""; $("password").value="";
  });
  addEventListener("pageshow",event=>{if (event.persisted) {clearPrivate(); bootstrap();}});
  function viewportHeight() {
    const height=window.visualViewport?.height || window.innerHeight;
    document.documentElement.style.setProperty("--viewport-height",`${Math.round(height)}px`);
  }
  window.visualViewport?.addEventListener("resize",viewportHeight);
  addEventListener("resize",viewportHeight); viewportHeight();
  setInterval(controls,1000);
  setInterval(async()=>{
    if (document.hidden || !state.session || state.background || Date.now()<state.cooldown) return;
    state.background=true;
    try {await refreshChat();} catch(e) {status(errorText(e));} finally {state.background=false;}
  },15000);
  setInterval(()=>{if (!document.hidden && state.session && Date.now()>=state.cooldown) ready();},30000);
  setInterval(()=>{if (!document.hidden && state.session && !state.authBusy && Date.now()>=state.cooldown) bootstrap();},60000);
  bootstrap();
}
