import {t, errorMessage, statusLabel, setLanguage, locale, languageForBrowser, translateStatic} from "./i18n.js";
// Private browser client. No credentials, drafts or history in browser storage.
const API = "/api/v1";
const TERMINAL = new Set(["completed", "truncated", "failed", "interrupted"]);

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
    super(errorMessage(code));
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
        if (response.status === 401 && !quiet && state.session) clearPrivate(errorMessage("authentication_required"));
        throw new APIError(response.status,code,delay);
      }
      return data;
    } finally { clearTimeout(deadline); }
  }
  function errorText(error) {
    if (error instanceof APIError) return errorMessage(error.code)+(error.retryAfter?" "+t("error.retry_after",{seconds:error.retryAfter}):"");
    return t("error.connection");
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
      before:null,pending:null,ready:false,loading:false,preferences:null,sourceContext:null});
    $("messages").replaceChildren(); $("chat-list").replaceChildren(); $("source-preview").replaceChildren(); $("source-preview").hidden=true;
    $("message-input").value=""; $("password").value=""; $("use-memory").checked=true; $("account-name").textContent="";
    $("chat-title").textContent=t("chat.title"); $("generation-info").textContent="";
    $("model-status").textContent=t("model.checking"); $("new-title").value=t("dialog.default");
    $("create-dialog").close(); $("workspace").hidden=true; $("login-screen").hidden=false;
    $("login-status").textContent=message; $("connect-button").hidden=false;
    $("login-button").disabled=true; status(""); drawer(false); controls();
  }
  function applyUILanguage(language,force=false) {
    const changed=document.documentElement.lang!==language;
    setLanguage(language); document.documentElement.lang=language;
    $("login-language").value=language; $("ui-language").value=language;
    if (!changed && !force) return;
    translateStatic(document);
    document.querySelector('meta[name="apple-mobile-web-app-title"]').content=t("brand.name");
    document.querySelector('link[rel="manifest"]').href=`/manifest.webmanifest?lang=${language}`;
    $("chat-title").textContent=state.chat?.title || t("chat.title");
    if (state.ready) $("model-status").textContent=t("model.ready",{model:state.model || "qwen2.5:14b"});
    if (!state.session && state.csrf) $("login-status").textContent=t("login.required");
    renderChats(); renderHistory();
    if (state.sourceContext) renderSourceContext(state.sourceContext,state.sourceMessage);
  }
  function applyPreferences(value) {
    state.preferences=value; applyUILanguage(value.ui_language);
    $("reply-language").value=value.reply_language;
  }
  async function loadPreferences() {
    const owner=state.session?.id;
    if (!owner || state.prefSaving) return;
    const value=await api("/preferences");
    if (state.session?.id===owner && !state.prefSaving) applyPreferences(value);
  }
  async function savePreferences() {
    if (!state.session || !state.preferences || state.prefSaving) return;
    const owner=state.session.id;
    const body={ui_language:$("ui-language").value,reply_language:$("reply-language").value,expected_revision:state.preferences.revision};
    state.prefSaving=true; controls();
    try {
      const value=await api("/preferences",{method:"PATCH",body});
      if (state.session?.id===owner) {applyPreferences(value);status(t("settings.saved"));}
    } catch (e) {
      if (state.session?.id===owner) {
        // A lost PATCH response is uncertain: reload, do not replay stale settings.
        try {
          const value=await api("/preferences");
          if (state.session?.id===owner) applyPreferences(value);
        } catch {
          if (state.session?.id===owner && state.preferences) applyPreferences(state.preferences);
        }
        if (state.session?.id===owner) status(e instanceof APIError?errorText(e):t("settings.failed"));
      }
    } finally {state.prefSaving=false; controls();}
  }
  function controls() {
    const bytes=messageBytes($("message-input").value);
    $("message-size").textContent=t("chat.bytes",{count:bytes.toLocaleString(locale())});
    const busy = state.messages.some(m=>m.role==="assistant" && !TERMINAL.has(m.status));
    $("use-memory").disabled=state.mutating || Boolean(state.pending);
    for (const id of ["ui-language","reply-language"]) $(id).disabled=state.prefSaving || state.mutating || Boolean(state.pending) || !state.preferences;
    $("message-input").disabled=!state.chat || state.loading || state.mutating || Boolean(state.pending);
    $("send-button").disabled=!state.chat || !state.ready || busy || state.loading || state.mutating || state.prefSaving || !state.preferences || Boolean(state.pending)
      || !$("message-input").value.trim() || bytes>16384 || Date.now()<state.cooldown;
    $("new-chat").disabled=state.mutating || Boolean(state.pending);
    $("delivery-notice").hidden=!state.pending || state.mutating;
    $("replay-request").disabled=state.mutating || Date.now()<state.cooldown;
    const last=state.messages.at(-1);
    $("retry-generation").hidden=!(last?.role==="assistant" && ["truncated","failed","interrupted"].includes(last.status));
    $("retry-generation").disabled=!state.ready || state.mutating || state.prefSaving || !state.preferences || Boolean(state.pending) || state.loading || Date.now()<state.cooldown;
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
      const date=document.createElement("small"); date.textContent=new Date(chat.created_at).toLocaleDateString(locale());
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
    label.textContent=message.role==="user"?t("chat.you"):t("brand.name");
    const text=document.createElement("pre"); text.className="message-text"; text.textContent=message.content;
    const info=document.createElement("div"); info.className="message-state";
    info.textContent=message.role==="assistant"?statusLabel(message.status):"";
    node.append(label,text,info);
    if (message.memory?.enabled) {
      const details=document.createElement("details"); details.className="memory-sources";
      const summary=document.createElement("summary");
      summary.textContent=t("memory.sources",{count:message.memory.sources.length});
      details.append(summary);
      if (!message.memory.sources.length) {
        const note=document.createElement("p"); note.textContent=t("memory.empty");
        details.append(note);
      }
      message.memory.sources.forEach((source,i)=>{
        const author=source.role==="assistant"?t("brand.name"):t("chat.you");
        const partial=source.role==="assistant" && source.status!=="completed"?` · ${statusLabel(source.status)}`:"";
        const link=document.createElement("a"); link.textContent=`[M${i+1}] ${author} · ${t("memory.message",{sequence:source.sequence})}${partial}`;
        link.href=`#chat=${source.chat_id}&message=${source.message_id}`;
        const quote=document.createElement("blockquote"); quote.textContent=source.quote;
        details.append(link,quote);
      });
      node.append(details);
    }
    return node;
  }
  function renderHistory() {
    $("messages").replaceChildren(...state.messages.map(messageNode));
    $("empty-state").hidden=state.messages.length>0;
    controls();
  }
  function renderSourceContext(context,sourceMessage) {
    const panel=$("source-preview"); panel.replaceChildren();
    const heading=document.createElement("strong"); heading.textContent=t("memory.conversation");panel.append(heading);
    for (const source of context.items) {
      const item=document.createElement("section"),label=document.createElement("p");
      label.textContent=`${source.id===sourceMessage?t("memory.anchor")+" · ":""}${source.role==="user"?t("chat.you"):t("brand.name")} · ${t("memory.message",{sequence:source.sequence})} · ${new Date(source.created_at).toLocaleString(locale())} · ${statusLabel(source.status)}`;
      const quote=document.createElement("pre");quote.className="message-text";quote.textContent=source.content;
      item.append(label,quote);panel.append(item);
    }
    const note=document.createElement("p");note.textContent=t("memory.window");panel.append(note);panel.hidden=false;
  }
  async function openChat(id, sourceMessage=null) {
    if (!safeId(id) || !state.session) return;
    stopWatch(); const view=++state.view; state.loading=true; state.chat=null;
    state.messages=[]; state.before=null; state.sourceContext=null; $("source-preview").replaceChildren(); $("source-preview").hidden=true; renderHistory(); controls(); drawer(false);
    try {
      const page=await api(`/chats/${id}/messages?latest=true&limit=50`);
      const chat=await api("/chats/"+id);
      if (view!==state.view || !state.session) return;
      state.chat=chat; state.messages=page.items; state.before=page.next_before_sequence;
      $("chat-title").textContent=chat.title; $("generation-info").textContent="";
      history.replaceState(null,"",`#chat=${id}`); renderChats(); renderHistory(); scrollBottom();
      watchOutstanding();
      if (sourceMessage && safeId(sourceMessage)) {
        const context=await api(`/chats/${id}/messages/${sourceMessage}/context`);
        if (view!==state.view || !state.session) return;
        // Keep the paginated timeline complete; show an older source separately.
        state.sourceContext=context;state.sourceMessage=sourceMessage;
        renderSourceContext(context,sourceMessage);
        const panel=$("source-preview");
        panel.scrollIntoView({block:"nearest"});
        history.replaceState(null,"",`#chat=${id}&message=${sourceMessage}`);
      }
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
    const row={...data.assistant,generation_id:data.id,error_code:data.error_code,memory:data.context?.memory};
    state.messages=mergeMessages(state.messages,[row]);
    let node=[...$("messages").children].find(n=>n.dataset.messageId===row.id);
    if (node) node.replaceWith(messageNode(row)); else $("messages").append(messageNode(row));
    $("empty-state").hidden=true;
    const omitted=data.context?.omitted_turns || 0;
    $("generation-info").textContent=statusLabel(data.status)+(omitted?" · "+t("chat.omitted",{count:omitted}):"");
    if (data.error_code) status(errorMessage(data.error_code));
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
      $("generation-info").textContent=t("chat.polling");
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
      if (code==="authentication_required") clearPrivate(errorMessage("authentication_required")); else fallback();
    });
  }
  async function ready() {
    const owner=state.session?.id; if (!owner) return;
    try {
      const data=await api("/health/ready");
      if (state.session?.id!==owner) return;
      state.ready=data.status==="ready";
      state.model=data.profile.model;
      $("model-status").textContent=t("model.ready",{model:data.profile.model});
    } catch (e) {
      if (state.session?.id!==owner) return;
      state.ready=false; $("model-status").textContent=e instanceof APIError && e.status===503
        ?t("model.unavailable"):t("model.check_failed");
    }
    controls();
  }
  async function bootstrap() {
    if (state.authBusy) return;
    state.authBusy=true; $("login-button").disabled=true;
    try {
      const data=await api("/auth/session",{quiet:true});
      if (state.session && data.user?.id!==state.session.id) clearPrivate(t("login.changed"));
      state.csrf=data.csrf_token;
      if (data.user) await signedIn(data.user);
      else {state.session=null; $("login-status").textContent=t("login.required"); $("connect-button").hidden=true;}
    } catch (e) { $("login-status").textContent=errorText(e); $("connect-button").hidden=false; }
    finally {state.authBusy=false; $("login-button").disabled=!state.csrf;}
  }
  async function signedIn(user) {
    state.session=user; $("account-name").textContent=user.username;
    $("login-screen").hidden=true; $("workspace").hidden=false; $("password").value="";
    await loadPreferences(); await loadChats();
    const route=location.hash.match(/^#chat=([a-f0-9]{32})(?:&message=([a-f0-9]{32}))?$/);
    const requested=route?.[1];
    if (!state.chat && requested) {
      try {await openChat(requested,route?.[2]);} catch(e) {status(errorText(e)); history.replaceState(null,"",location.pathname);}
    }
    await ready();
  }
  async function login(event) {
    event.preventDefault(); if (state.authBusy || !state.csrf) return;
    state.authBusy=true; $("login-button").disabled=true;
    try {
      const data=await api("/auth/login",{method:"POST",body:{username:$("username").value,password:$("password").value},quiet:true});
      state.csrf=data.csrf_token; await signedIn(data.user);
    } catch (e) { $("login-status").textContent=e instanceof APIError && e.status===401?t("login.invalid"):errorText(e); }
    finally {$("password").value=""; state.authBusy=false; $("login-button").disabled=!state.csrf;}
  }
  async function deliver() {
    const operation=state.pending; if (!operation || state.mutating || !state.session) return;
    state.mutating=true; controls(); status(t("chat.sending"));
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
    try { await api("/auth/logout",{method:"POST",body:{}}); clearPrivate(t("login.logged_out")); }
    catch (e) {status(errorText(e));}
    finally {state.authBusy=false; if (!state.session) bootstrap();}
  });
  $("new-chat").addEventListener("click",()=>{ $("new-title").value=t("dialog.default"); $("create-dialog").showModal(); });
  $("cancel-create").addEventListener("click",()=>$("create-dialog").close());
  $("create-form").addEventListener("submit",event=>{
    event.preventDefault(); const title=$("new-title").value.trim(); if (!title) return;
    $("create-dialog").close(); startOperation("/chats",{title},"create");
  });
  $("composer").addEventListener("submit",event=>{
    event.preventDefault(); if ($("send-button").disabled) return;
    startOperation(`/chats/${state.chat.id}/messages`,{content:$("message-input").value,expected_revision:state.chat.revision,use_memory:$("use-memory").checked,reply_language:state.preferences.reply_language},"send");
  });
  $("message-input").addEventListener("input",controls);
  $("message-input").addEventListener("keydown",event=>{
    if (event.key==="Enter" && !event.shiftKey && !event.isComposing && matchMedia("(pointer:fine)").matches) {
      event.preventDefault(); $("composer").requestSubmit();
    }
  });
  $("retry-generation").addEventListener("click",()=>{
    const user=[...state.messages].reverse().find(m=>m.role==="user"); if (!user) return;
    startOperation(`/messages/${user.id}/retry`,{expected_revision:state.chat.revision,use_memory:$("use-memory").checked,reply_language:state.preferences.reply_language},"retry");
  });
  $("replay-request").addEventListener("click",deliver);
  $("discard-request").addEventListener("click",async()=>{
    if (!confirm(t("delivery.confirm"))) return;
    try {
      if (state.chat) await refreshChat(true); await loadChats();
      state.pending=null; $("message-input").value=""; status(t("delivery.check_history")); controls();
    } catch(e) {status(errorText(e));}
  });
  $("refresh-chats").addEventListener("click",()=>loadChats().catch(e=>status(errorText(e))));
  $("more-chats").addEventListener("click",()=>loadChats(true).catch(e=>status(errorText(e))));
  $("refresh-chat").addEventListener("click",()=>Promise.all([refreshChat(true),ready(),loadPreferences()]).catch(e=>status(errorText(e))));
  $("login-language").addEventListener("change",()=>applyUILanguage($("login-language").value));
  $("ui-language").addEventListener("change",savePreferences);
  $("reply-language").addEventListener("change",savePreferences);
  $("older-messages").addEventListener("click",()=>older().catch(e=>status(errorText(e))));
  $("menu-button").addEventListener("click",()=>drawer(!$("workspace").classList.contains("drawer-open")));
  $("drawer-backdrop").addEventListener("click",()=>{drawer(false); $("menu-button").focus();});
  document.addEventListener("keydown",event=>{if (event.key==="Escape") drawer(false);});
  addEventListener("hashchange",()=>{
    const route=location.hash.match(/^#chat=([a-f0-9]{32})(?:&message=([a-f0-9]{32}))?$/);
    if (route) openChat(route[1],route[2]).catch(e=>status(errorText(e)));
  });
  document.addEventListener("visibilitychange",()=>{
    if (document.hidden) stopWatch(); else if (state.session) bootstrap().then(()=>refreshChat(true)).catch(e=>status(errorText(e)));
  });
  addEventListener("online",()=>{if (state.session) refreshChat(true).then(ready).catch(e=>status(errorText(e))); else bootstrap();});
  addEventListener("offline",()=>status(t("chat.offline")));
  addEventListener("beforeunload",event=>{
    if (state.pending || $("message-input").value.trim()) {event.preventDefault(); event.returnValue="";}
  });
  addEventListener("pagehide",()=>{
    stopWatch(); $("messages").replaceChildren(); $("chat-list").replaceChildren(); $("source-preview").replaceChildren(); $("source-preview").hidden=true;
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
  applyUILanguage(languageForBrowser(navigator.languages),true);
  bootstrap();
}
