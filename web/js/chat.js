"use strict";
/* The Nova AI screen: a clean chat that streams answers, accepts files and pictures,
   summarizes them, and turns them into quizzes. */

const ACCEPT = ".png,.jpg,.jpeg,.webp,.gif,.pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.json,.py,.js,.html,.css,.java,.c,.cpp,.cs,.sql,.xml,.yml,.yaml,.tex,.log";
const MAX_FILE = 12 * 1024 * 1024, MAX_FILES = 5;
const MODES = [["chat", "Chat"], ["explain", "Explain simply"], ["summarize", "Summarize"], ["steps", "Step by step"]];
const Chat = { threadId: null, files: [], mode: "chat", busy: false, abort: null, consent: false, afterPick: null };

function extOf(name) { return (name.split(".").pop() || "").toLowerCase(); }
function kindOf(name) { const e = extOf(name); return ["png", "jpg", "jpeg", "webp", "gif"].includes(e) ? "image" : e === "pdf" ? "pdf" : "doc"; }

/** Draw an AI answer. Quiz cards saved in the text are drawn as interactive cards. */
function renderAnswer(target, text, streaming) {
  target.classList.toggle("caret", !!streaming);
  const parts = text.split(/```nova-quiz\n([\s\S]*?)\n```/);
  target.replaceChildren();
  parts.forEach((part, i) => {
    if (i % 2 === 0) { if (part.trim()) target.insertAdjacentHTML("beforeend", md(part)); return; }
    try { target.append(quizCard(JSON.parse(part))); } catch { /* a quiz that did not finish saving is skipped */ }
  });
  $$("pre .copy", target).forEach((b) => b.addEventListener("click", () => { copyText(b.parentElement.querySelector("code").textContent); b.textContent = "Copied"; setTimeout(() => (b.textContent = "Copy"), 1400); }));
}

/** An interactive quiz that shows up inside the chat. */
function quizCard(questions) {
  const card = h("div", { class: "qz glass glass-2" });
  let index = 0, score = 0;
  const draw = () => {
    card.replaceChildren();
    if (index >= questions.length) {
      const p = Math.round(100 * score / questions.length);
      card.append(h("div", { class: "qz-top" }, h("h4", {}, "Quiz finished"), h("span", { class: "chip " + (p >= 70 ? "green" : "red") }, `${score} of ${questions.length} (${p}%)`)),
        h("p", {}, p >= 80 ? "Strong work. Try the harder version next." : p >= 50 ? "Good start. Review the ones you missed, then try again." : "This is a useful map of what to study next."),
        h("div", { class: "row-gap", style: { marginTop: "12px" } },
          h("button", { class: "btn btn-sm", onclick: () => { index = 0; score = 0; draw(); } }, icon("refresh"), "Try again"),
          h("button", { class: "btn btn-sm btn-primary", onclick: () => saveQuizDialog(questions) }, icon("plus"), "Save to my subjects")));
      return;
    }
    const q = questions[index]; let answered = false;
    const explain = h("div", { class: "why", hidden: true });
    const next = h("button", { class: "btn btn-sm btn-primary", hidden: true, onclick: () => { index++; draw(); } }, index + 1 === questions.length ? "See score" : "Next");
    const buttons = q.choices.map((choice, n) => h("button", { class: "choice", type: "button", onclick: () => {
      if (answered) return; answered = true;
      const right = n + 1 === q.correct; if (right) score++;
      buttons.forEach((b, m) => { b.disabled = true; if (m + 1 === q.correct) b.classList.add("right"); else if (m === n) b.classList.add("wrong"); });
      explain.textContent = (right ? "Correct. " : "Not quite. ") + (q.explanation || ""); explain.hidden = false; next.hidden = false; next.focus();
    } }, h("span", { class: "k" }, "ABCD"[n]), h("span", {}, choice)));
    card.append(h("div", { class: "qz-top" }, h("h4", {}, `Question ${index + 1} of ${questions.length}`), h("span", { class: "chip blue" }, "Practice quiz")),
      h("div", { class: "bar", style: { margin: "6px 0 14px" } }, h("i", { style: { width: `${100 * index / questions.length}%` } })),
      h("div", { class: "q-text", style: { fontSize: "1.1rem", margin: "0 0 14px" } }, q.question), h("div", { class: "choices" }, buttons), explain, h("div", { style: { marginTop: "12px", textAlign: "right" } }, next));
  };
  draw();
  return card;
}

async function saveQuizDialog(questions) {
  const subjects = await api("list_subjects").catch(() => []);
  const form = buildForm([
    { name: "subject", label: "Subject", type: "select", options: [...subjects.map((s) => ({ value: s.id, label: s.name })), { value: "new", label: "New subject..." }], value: subjects[0]?.id ?? "new" },
    { name: "newName", label: "New subject name", value: "AI quizzes", max: 80 },
    { name: "topic", label: "Topic", value: "From my file", max: 80, hint: "Saved questions appear in Practice Quizzes and My Progress." },
  ]);
  const toggle = () => { form.inputs.newName.parentElement; const isNew = form.inputs.subject.value === "new"; form.inputs.newName.hidden = !isNew; form.inputs.newName.previousElementSibling.hidden = !isNew; };
  form.inputs.subject.addEventListener("change", toggle); toggle();
  await openSheet({ title: "Save these questions", body: form.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => {
    const v = form.values();
    const result = await api("save_generated_quiz", v.subject === "new" ? null : Number(v.subject), v.newName, v.topic, questions);
    toast("Saved", `${plural(result.saved, "question")} added to Practice Quizzes.`);
  } }] });
}

async function viewChat(view) {
  view.classList.add("fill");
  Chat.files = []; Chat.busy = false; Chat.abort = null;
  const status = await api("ai_status").catch(() => ({ configured: false }));

  const msgsIn = h("div", { class: "msgs-in" });
  const msgs = h("div", { class: "msgs scroll" }, msgsIn);
  const jump = h("button", { class: "btn btn-sm jump glass-2", onclick: () => stick(true) }, icon("up", ""), "Latest");
  jump.querySelector("svg").style.transform = "rotate(180deg)";
  const title = h("div", { class: "t grow" }, "New chat");
  const threadsBox = h("div", { class: "threads glass glass-2" });
  const drop = h("div", { class: "drop" }, h("div", {}, icon("upload", ""), h("div", {}, "Drop files or pictures to add them")));
  let pinned = true;

  const distance = () => msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight;
  msgs.addEventListener("scroll", () => { pinned = distance() < 90; jump.classList.toggle("show", !pinned && distance() > 220); }, { passive: true });
  function stick(force) { if (force) pinned = true; if (pinned) requestAnimationFrame(() => { msgs.scrollTop = msgs.scrollHeight; }); }
  new ResizeObserver(() => stick()).observe(msgsIn);

  /* ----- composer ----- */
  const text = h("textarea", { rows: 1, placeholder: "Ask anything, or attach notes, slides, a PDF or a photo...", "aria-label": "Message Nova" });
  const picker = h("input", { type: "file", multiple: true, accept: ACCEPT, hidden: true });
  const sendBtn = h("button", { class: "btn btn-primary icon-btn", type: "button", "aria-label": "Send", onclick: () => (Chat.busy ? stop() : send()) });
  const attachRow = h("div", { class: "attach-row" }), quick = h("div", { class: "quick" }), modesRow = h("div", { class: "modes", role: "group", "aria-label": "Answer style" });
  const composer = h("div", { class: "composer glass glass-2" });
  const popHost = h("div", { style: { position: "relative" } });
  composer.append(popHost, attachRow, quick, modesRow, h("div", { class: "compose-row" },
    h("button", { class: "btn btn-ghost icon-btn", type: "button", "aria-label": "Attach files or pictures", title: "Attach files or pictures", onclick: () => picker.click() }, icon("clip")), text, sendBtn), picker);

  const fit = () => { text.style.height = "auto"; text.style.height = Math.min(190, text.scrollHeight) + "px"; };
  const paintSend = () => { sendBtn.replaceChildren(icon(Chat.busy ? "stop" : "up")); sendBtn.setAttribute("aria-label", Chat.busy ? "Stop" : "Send"); };
  const paintModes = () => modesRow.replaceChildren(...MODES.map(([key, label]) => h("button", { class: "mode", type: "button", "aria-pressed": String(Chat.mode === key), onclick: () => { Chat.mode = key; paintModes(); text.focus(); } }, label)));
  function paintAttach() {
    attachRow.replaceChildren(...Chat.files.map((f, i) => h("div", { class: "attach" },
      f.kind === "image" ? h("img", { src: f.url, alt: "" }) : h("span", { class: "ico" }, extOf(f.name).slice(0, 4).toUpperCase()),
      h("span", {}, h("span", { class: "nm" }, f.name), h("small", {}, bytes(f.file.size))),
      h("button", { class: "x", type: "button", "aria-label": `Remove ${f.name}`, onclick: () => { Chat.files.splice(i, 1); paintAttach(); } }, icon("x")))));
    attachRow.hidden = !Chat.files.length;
    quick.hidden = !Chat.files.length || Chat.busy;
    if (Chat.files.length) quick.replaceChildren(
      h("button", { class: "btn btn-sm", type: "button", onclick: () => send("Summarize this.", "summarize") }, icon("list"), "Summarize"),
      h("button", { class: "btn btn-sm", type: "button", onclick: quizPopover }, icon("quiz"), "Make a quiz"),
      h("button", { class: "btn btn-sm", type: "button", onclick: () => send("Explain this to me simply.", "explain") }, icon("bulb"), "Explain simply"));
  }
  function addFiles(list) {
    for (const file of [...list]) {
      if (Chat.files.length >= MAX_FILES) { toast("Too many files", `Attach up to ${MAX_FILES} at a time.`, "bad"); break; }
      if (file.size > MAX_FILE) { toast("File too large", `${file.name} is over ${bytes(MAX_FILE)}.`, "bad"); continue; }
      if (!ACCEPT.split(",").includes("." + extOf(file.name))) { toast("Cannot read that", `${file.name}: try a PDF, picture, Word, PowerPoint or text file.`, "bad"); continue; }
      if (Chat.files.some((f) => f.name === file.name && f.file.size === file.size)) continue;
      Chat.files.push({ name: file.name, file, kind: kindOf(file.name), url: kindOf(file.name) === "image" ? URL.createObjectURL(file) : null });
    }
    paintAttach(); text.focus();
    if (Chat.afterPick && Chat.files.length) { const what = Chat.afterPick; Chat.afterPick = null; if (what === "quiz") quizPopover(); else send("Summarize this.", "summarize"); }
  }
  picker.addEventListener("change", () => { addFiles(picker.files); picker.value = ""; });
  text.addEventListener("input", fit);
  text.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!Chat.busy) send(); } });
  text.addEventListener("paste", (e) => { const files = [...(e.clipboardData?.files || [])]; if (files.length) { e.preventDefault(); addFiles(files.map((f, i) => (f.name && f.name !== "image.png") ? f : new File([f], `pasted-${Date.now()}-${i}.png`, { type: f.type })) ); } });
  let dragDepth = 0;
  view.addEventListener("dragenter", (e) => { if ([...(e.dataTransfer?.types || [])].includes("Files")) { dragDepth++; drop.classList.add("show"); composer.classList.add("drag"); } });
  view.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; drop.classList.remove("show"); composer.classList.remove("drag"); } });
  view.addEventListener("dragover", (e) => e.preventDefault());
  view.addEventListener("drop", (e) => { e.preventDefault(); dragDepth = 0; drop.classList.remove("show"); composer.classList.remove("drag"); addFiles(e.dataTransfer.files); });

  function quizPopover() {
    if (popHost.firstChild) { popHost.replaceChildren(); return; }
    let count = 8, level = "mixed";
    const seg = (options, current, set) => h("div", { class: "seg" }, options.map(([v, l]) => h("button", { type: "button", "aria-pressed": String(current() === v), onclick: (e) => { set(v); $$("button", e.currentTarget.parentElement).forEach((b) => b.setAttribute("aria-pressed", "false")); e.currentTarget.setAttribute("aria-pressed", "true"); } }, l)));
    popHost.append(h("div", { class: "pop glass glass-2" }, h("h4", {}, "Questions"), seg([[5, "5"], [8, "8"], [10, "10"], [15, "15"]], () => count, (v) => (count = v)),
      h("h4", { style: { marginTop: "12px" } }, "Difficulty"), seg([["easy", "Easy"], ["mixed", "Mixed"], ["hard", "Hard"]], () => level, (v) => (level = v)),
      h("button", { class: "btn btn-primary btn-sm", style: { marginTop: "14px", width: "100%" }, type: "button", onclick: () => { popHost.replaceChildren(); makeQuiz(count, level); } }, icon("sparkles"), "Create quiz")));
  }

  /* ----- messages ----- */
  function fileBlock(files) {
    return files.length ? h("div", { class: "file-pills" }, files.map((f) => h("div", { class: "file-pill glass glass-2" },
      f.url ? h("img", { src: f.url, alt: "" }) : h("span", { class: "ico" }, icon(f.kind === "image" ? "image" : "file")), h("span", {}, f.name)))) : null;
  }
  function userMsg(content, files) {
    const node = h("div", { class: "msg user" }, h("div", { style: { display: "flex", flexDirection: "column", alignItems: "flex-end", maxWidth: "100%" } }, fileBlock(files), content ? h("div", { class: "bubble" }, content) : null));
    msgsIn.append(node); return node;
  }
  function aiMsg(content = "", streaming = false) {
    const star = novaStar("nova-av" + (streaming ? " think" : "")), body = h("div", { class: "ai-body" });
    const actions = h("div", { class: "ai-actions" }, h("button", { type: "button", onclick: () => { copyText(body.dataset.raw || body.textContent); toast("Copied", "", "good", 1.6); } }, icon("copy"), "Copy"));
    const node = h("div", { class: "msg" }, star, h("div", { class: "grow", style: { minWidth: 0, flex: 1 } }, body, actions));
    actions.hidden = streaming; body.dataset.raw = content; renderAnswer(body, content, streaming); msgsIn.append(node);
    return { node, body, star, actions, set(t, live) { body.dataset.raw = t; renderAnswer(body, t, live); }, done() { star.classList.remove("think"); actions.hidden = false; body.classList.remove("caret"); } };
  }
  function errorMsg(message) { msgsIn.append(h("div", { class: "msg" }, novaStar("nova-av"), h("div", { class: "ai-error", role: "alert" }, message))); stick(); }
  function welcome() {
    msgsIn.replaceChildren(h("div", { class: "welcome" }, novaStar("big-logo"), h("h2", {}, `${greeting()}${S.firstName ? ", " + S.firstName : ""}.`), h("p", {}, "I can explain hard ideas, summarize your notes, and turn any file or photo into a quiz."),
      !status.configured ? h("div", { class: "card glass glass-2", style: { marginTop: "20px", textAlign: "left" } }, h("strong", { style: { color: "var(--ink)" } }, "Connect your AI first"), h("p", { class: "sub" }, "Paste a free Gemini key (or a Claude key) in Settings. It stays on this computer."), h("button", { class: "btn btn-primary btn-sm", style: { marginTop: "12px" }, onclick: () => go("settings") }, icon("sliders"), "Open AI settings")) : null,
      h("div", { class: "suggest" },
        sug("file", "Summarize a file", "Slides, PDFs, notes or a photo of a page", () => { Chat.afterPick = "summarize"; picker.click(); }),
        sug("quiz", "Quiz me from my notes", "Upload anything, get practice questions", () => { Chat.afterPick = "quiz"; picker.click(); }),
        sug("bulb", "Explain a hard term", "Plain words and a real-life comparison", () => { Chat.mode = "explain"; paintModes(); text.value = "Explain simply: "; fit(); text.focus(); }),
        sug("list", "Solve step by step", "Get the method, not just the answer", () => { Chat.mode = "steps"; paintModes(); text.focus(); }))));
  }
  const sug = (ic, t, s, fn) => h("button", { class: "glass glass-2", type: "button", onclick: fn }, icon(ic), h("b", {}, t), h("span", {}, s));

  /* ----- sending ----- */
  async function agree() {
    if (Chat.consent || localStorage.getItem("nova_ai_ok") === "1") return true;
    const ok = await confirmBox("Before you send", status.disclosure || "Your message will be sent to an AI service over the internet. Continue?", "Continue", false);
    if (ok) { Chat.consent = true; try { localStorage.setItem("nova_ai_ok", "1"); } catch { /* it just asks again next time */ } }
    return ok;
  }
  async function pack() { return Promise.all(Chat.files.map(async (f) => ({ name: f.name, data: await fileToBase64(f.file) }))); }
  function begin(content) {
    if (msgsIn.querySelector(".welcome")) msgsIn.replaceChildren();
    const shown = Chat.files.map((f) => ({ name: f.name, kind: f.kind, url: f.url }));
    userMsg(content, shown); Chat.files = []; paintAttach(); text.value = ""; fit(); stick(true);
  }
  function busy(on) { Chat.busy = on; paintSend(); paintAttach(); }
  function stop() { if (Chat.abort) Chat.abort.abort(); }

  async function send(forced, forcedMode) {
    if (Chat.busy) return;
    const content = (forced ?? text.value).trim();
    if (!content && !Chat.files.length) return;
    if (!(await agree())) return;
    const mode = forcedMode || Chat.mode;
    let files;
    try { files = await pack(); } catch (e) { toast("Could not read the file", e.message, "bad"); return; }
    begin(content); busy(true);
    const reply = aiMsg("", true); let full = "", queued = 0;
    Chat.abort = new AbortController();
    try {
      const res = await post("/api/chat", { thread_id: Chat.threadId, text: content, mode, files }, Chat.abort.signal);
      if (!(res.headers.get("content-type") || "").includes("ndjson")) { const j = await res.json(); throw new Error(j.error || "Nova could not send that."); }
      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = "";
      for (;;) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop();
        for (const line of lines.filter(Boolean)) {
          const event = JSON.parse(line);
          if (event.t === "thread") { Chat.threadId = event.id; }
          else if (event.t === "delta") { full += event.text; if (!queued) queued = requestAnimationFrame(() => { queued = 0; reply.set(full, true); stick(); }); }
          else if (event.t === "error") throw new Error(event.message);
        }
      }
      cancelAnimationFrame(queued); reply.set(full, false); reply.done();
      if (!full.trim()) { reply.node.remove(); errorMsg("Nova got an empty answer. Please try again."); }
    } catch (error) {
      cancelAnimationFrame(queued);
      if (error.name === "AbortError") { full.trim() ? (reply.set(full, false), reply.done()) : reply.node.remove(); }
      else { full.trim() ? (reply.set(full, false), reply.done()) : reply.node.remove(); errorMsg(error.message || "Something went wrong. Please try again."); }
    } finally { Chat.abort = null; busy(false); stick(); title.textContent = title.textContent === "New chat" ? (content || "New chat").slice(0, 60) : title.textContent; loadThreads(); text.focus(); }
  }

  async function makeQuiz(count, difficulty) {
    if (Chat.busy) return;
    if (!(await agree())) return;
    const content = text.value.trim(); let files;
    try { files = await pack(); } catch (e) { toast("Could not read the file", e.message, "bad"); return; }
    begin(content || `Make a ${count}-question quiz from this.`); busy(true);
    const reply = aiMsg("Writing your quiz...", true);
    try {
      const res = await post("/api/quiz", { thread_id: Chat.threadId, text: content, files, count, difficulty });
      const j = await res.json(); if (!j.ok) throw new Error(j.error);
      Chat.threadId = j.data.thread_id; reply.set(`Here is a ${j.data.questions.length}-question quiz. Pick an answer to see why it is right.\n\n\`\`\`nova-quiz\n${JSON.stringify(j.data.questions)}\n\`\`\``, false); reply.done();
    } catch (error) { reply.node.remove(); errorMsg(error.message || "Nova could not make that quiz."); }
    finally { busy(false); stick(true); loadThreads(); }
  }

  /* ----- history ----- */
  async function loadThreads() {
    const threads = await api("list_threads").catch(() => []);
    threadsBox.replaceChildren(h("div", { class: "row-gap", style: { padding: "2px 6px 8px", justifyContent: "space-between" } }, h("strong", { style: { color: "var(--ink)" } }, "Chats"),
      threads.length ? h("button", { class: "btn btn-ghost btn-sm", onclick: async () => { if (await confirmBox("Delete all chats?", "Every saved conversation will be removed from this computer.")) { await run("clear_chats"); newChat(); loadThreads(); } } }, "Clear all") : null),
      threads.length ? h("div", { class: "list" }, threads.map((t) => h("div", { class: "item clickable" + (t.id === Chat.threadId ? " selected" : ""), onclick: () => openThread(t) }, h("div", { class: "grow" }, h("div", { class: "t", style: { fontSize: ".92rem" } }, t.title), h("div", { class: "s" }, t.updated_at.slice(0, 16))),
        h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Delete chat", onclick: async (e) => { e.stopPropagation(); await run("delete_thread", t.id); if (t.id === Chat.threadId) newChat(); loadThreads(); } }, icon("trash"))))) : h("div", { class: "empty", style: { padding: "20px" } }, "No saved chats yet."));
  }
  async function openThread(thread) {
    if (Chat.busy) return;
    threadsBox.classList.remove("open"); Chat.threadId = thread.id; title.textContent = thread.title; msgsIn.replaceChildren();
    const { ok, data } = await run("get_messages", thread.id); if (!ok) return;
    for (const m of data) {
      if (m.role === "user") userMsg(m.content, m.files.map((f) => ({ name: f.name, kind: f.kind })));
      else { const a = aiMsg(m.content, false); a.done(); }
    }
    stick(true); loadThreads();
  }
  function newChat() { if (Chat.busy) return; Chat.threadId = null; Chat.files = []; title.textContent = "New chat"; paintAttach(); welcome(); threadsBox.classList.remove("open"); }

  /* ----- assemble ----- */
  const head = h("div", { class: "chat-head" },
    h("button", { class: "btn btn-sm", type: "button", onclick: () => { threadsBox.classList.toggle("open"); loadThreads(); } }, icon("history"), "History"),
    h("button", { class: "btn btn-sm", type: "button", onclick: newChat }, icon("plus"), "New chat"), title);
  const root = h("div", { class: "chat" }, head, threadsBox, msgs, jump, h("div", { class: "composer-wrap" }, composer, h("div", { class: "foot-note" }, "Nova can make mistakes. Check important facts with your teacher or textbook.")), drop);
  view.replaceChildren(root);
  paintSend(); paintModes(); paintAttach(); welcome(); fit();
  document.addEventListener("click", (e) => { if (!threadsBox.contains(e.target) && !head.contains(e.target)) threadsBox.classList.remove("open"); if (!composer.contains(e.target)) popHost.replaceChildren(); });
  if (Chat.threadId === null && S.openThread) { openThread(S.openThread); S.openThread = null; }
  if (S.prefill) { text.value = S.prefill.text; Chat.mode = S.prefill.mode || "chat"; S.prefill = null; paintModes(); fit(); }
  setTimeout(() => text.focus(), 80);
}
