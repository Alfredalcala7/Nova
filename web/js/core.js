"use strict";
/* Small shared helpers: building elements, talking to the server, icons, Markdown, dialogs and toasts. */

const TOKEN = document.querySelector('meta[name="nova-token"]').content;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Build an element: h("div", {class: "card", onclick: fn}, "text", childElement) */
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "html") el.innerHTML = value;
    else if (key === "style" && typeof value === "object") { for (const [k, v] of Object.entries(value)) k.startsWith("--") ? el.style.setProperty(k, v) : (el.style[k] = v); }
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return el;
}

/* ---------- talking to the server ---------- */
async function api(fn, ...args) {
  let response;
  try {
    response = await fetch("/api/call", { method: "POST", headers: { "Content-Type": "application/json", "X-Nova-Token": TOKEN }, body: JSON.stringify({ fn, args }) });
  } catch { throw new Error("Nova could not be reached. Close and reopen the app."); }
  let reply;
  try { reply = await response.json(); } catch { throw new Error("Nova sent a reply that could not be read."); }
  if (!reply.ok) throw new Error(reply.error || "Something went wrong.");
  return reply.data;
}
/** Like api(), but shows the problem as a toast instead of throwing. Returns {ok, data}. */
async function run(fn, ...args) {
  try { return { ok: true, data: await api(fn, ...args) }; }
  catch (error) { toast("Could not do that", error.message, "bad"); return { ok: false }; }
}
async function post(path, body, signal) {
  return fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Nova-Token": TOKEN }, body: JSON.stringify(body), signal });
}

/* ---------- icons ---------- */
const ICONS = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.2-4.4A8 8 0 1 1 21 12z"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5M9 7h6"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3.5"/><path d="M8 3v4M16 3v4M3 10h18"/>',
  quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01"/>',
  chart: '<path d="M4 20V11M10 20V4M16 20v-7M22 20H2"/>',
  bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z"/>',
  sliders: '<path d="M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M20 18h0"/><circle cx="15" cy="6" r="2.4"/><circle cx="9" cy="12" r="2.4"/><circle cx="17" cy="18" r="2.4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  clip: '<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
  up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="3" fill="currentColor"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3.5"/><circle cx="9" cy="10" r="2"/><path d="M21 17l-5-5-9 8"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="3"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
  sparkles: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  list: '<path d="M4 6h16M4 12h10M4 18h14"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  play: '<path d="M7 4.5v15l12-7.5z" fill="currentColor"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  alert: '<path d="M12 3l10 17H2z"/><path d="M12 10v4M12 17h.01"/>',
};
function icon(name, extra = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon " + extra);
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONS[name] || "";
  return svg;
}
const NOVA_STAR = '<path d="M50 6l7 37 37 7-37 7-7 37-7-37-37-7 37-7z"/><circle cx="50" cy="50" r="9" fill="#fff"/>';
function novaStar(cls) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100"); svg.setAttribute("class", cls); svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = NOVA_STAR;
  return svg;
}

/* ---------- small helpers ---------- */
const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const pct = (n) => `${Math.round(n)}%`;
const plural = (n, word, many) => `${n} ${n === 1 ? word : (many || word + "s")}`;
function bytes(n) { return n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`; }
function greeting() { const hour = new Date().getHours(); return hour < 5 ? "Still up" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"; }
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}
function copyText(text) {
  if (navigator.clipboard && window.isSecureContext !== false) return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  return Promise.resolve(fallbackCopy(text));
}
function fallbackCopy(text) {
  const box = h("textarea", { style: { position: "fixed", opacity: 0 } }); box.value = text; document.body.append(box); box.select();
  try { document.execCommand("copy"); } catch { /* nothing else to try */ } box.remove();
}

/* ---------- Markdown (small, safe: everything is escaped first) ---------- */
function inline(text) {
  const codes = [];
  text = text.replace(/`([^`\n]+)`/g, (_, code) => { codes.push(code); return `\u0000${codes.length - 1}\u0000`; });
  text = escapeHtml(text)
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return text.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${escapeHtml(codes[i])}</code>`);
}
function md(source) {
  const lines = String(source).replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  const isBlock = (l) => /^(\s*([-*+]|\d+[.)])\s+|#{1,4}\s|>|```|\s*\|.*\||(-{3,}|\*{3,})\s*$)/.test(l);
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = line.match(/^```(\w*)/);
    if (fence) {
      const code = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out.push(`<pre><button class="copy" type="button">Copy</button><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) { const n = heading[1].length; out.push(`<h${n}>${inline(heading[2])}</h${n}>`); i++; continue; }
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) { out.push("<hr>"); i++; continue; }
    if (/^>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^>/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote>${md(quote.join("\n"))}</blockquote>`); continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1] || "")) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(line); i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      out.push(`<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    const list = line.match(/^(\s*)([-*+]|\d+[.)])\s+/);
    if (list) {
      const ordered = /\d/.test(list[2]);
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
        if (m && /\d/.test(m[2]) === ordered && m[1].length < 2) { items.push([m[3]]); i++; }
        else if (m && m[1].length >= 2 && items.length) { items[items.length - 1].push(m[3]); i++; }   // a nested bullet stays inside its parent
        else if (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length) { items[items.length - 1][0] += " " + lines[i].trim(); i++; }
        else break;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.map(([first, ...nested]) => `<li>${inline(first)}${nested.length ? `<ul>${nested.map((n) => `<li>${inline(n)}</li>`).join("")}</ul>` : ""}</li>`).join("")}</${tag}>`);
      continue;
    }
    const para = [line]; i++;
    while (i < lines.length && lines[i].trim() && !isBlock(lines[i])) para.push(lines[i++]);
    out.push(`<p>${para.map(inline).join("<br>")}</p>`);
  }
  return out.join("");
}

/* ---------- toasts and dialogs ---------- */
function toast(title, message, kind = "good", seconds = 5) {
  const box = h("div", { class: "toast glass " + kind, role: "status" }, h("strong", {}, title), message ? h("span", {}, message) : null);
  $("#toasts").append(box);
  const close = () => { box.style.transition = "all .35s"; box.style.opacity = 0; box.style.transform = "translateX(30px)"; setTimeout(() => box.remove(), 350); };
  box.addEventListener("click", close);
  setTimeout(close, seconds * 1000);
}

/** Open a dialog. buttons: [{label, kind: "primary"|"danger"|"", run: async () => false to stay open}] */
function openSheet({ title, body, buttons = [], wide = false }) {
  const previous = document.activeElement;
  const error = h("div", { class: "err", role: "alert" });
  const sheet = h("div", { class: "sheet glass glass-2" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true", "aria-label": title },
    h("header", {}, h("h3", {}, title)), h("div", { class: "body" }, body, error),
    h("footer", {}, buttons.map((b) => h("button", { class: "btn " + (b.kind === "primary" ? "btn-primary" : b.kind === "danger" ? "btn-danger" : b.kind === "quiet" ? "btn-ghost" : ""), type: "button",
      onclick: async (event) => {
        const button = event.currentTarget; button.disabled = true; error.textContent = "";
        try { if ((b.run ? await b.run(error) : undefined) !== false) close(b.value); } catch (e) { error.textContent = e.message; }
        button.disabled = false;
      } }, b.label))));
  const scrim = h("div", { class: "modal-scrim", onmousedown: (e) => { if (e.target === scrim) close(); } }, sheet);
  let resolve; const done = new Promise((r) => (resolve = r));
  function close(value) { document.removeEventListener("keydown", onKey, true); scrim.style.opacity = 0; scrim.style.transition = "opacity .2s"; setTimeout(() => scrim.remove(), 200); previous && previous.focus && previous.focus(); resolve(value); }
  function onKey(e) {
    if (e.key === "Escape") { e.stopPropagation(); close(); }
    else if (e.key === "Enter" && !e.shiftKey && e.target.matches && e.target.matches("input:not([type=checkbox]):not([type=radio]), select")) {
      const primary = $(".btn-primary", sheet); if (primary) { e.preventDefault(); primary.click(); }
    }
  }
  document.addEventListener("keydown", onKey, true);
  $("#modal-root").append(scrim);
  setTimeout(() => ($("input:not([type=hidden]), textarea, select, .btn-primary", sheet) || sheet).focus(), 60);
  return done;
}
async function confirmBox(title, message, okLabel = "Delete", danger = true) {
  return (await openSheet({ title, body: h("p", { style: { padding: "6px 0 8px" } }, message),
    buttons: [{ label: "Cancel", kind: "quiet" }, { label: okLabel, kind: danger ? "primary" : "primary", value: true }] })) === true;
}

/** Build a form from a list of fields. Returns {el, values()}. */
function buildForm(fields) {
  const inputs = {};
  const el = h("div", {});
  for (const f of fields) {
    let input;
    if (f.type === "textarea") input = h("textarea", { class: "textarea", rows: f.rows || 3, maxlength: f.max, placeholder: f.placeholder || "" });
    else if (f.type === "select") input = h("select", { class: "select" }, (f.options || []).map((o) => h("option", { value: o.value ?? o }, o.label ?? o)));
    else input = h("input", { class: "field", type: f.type || "text", maxlength: f.max, placeholder: f.placeholder || "", autocomplete: "off" });
    input.value = f.value ?? "";
    input.id = "f-" + f.name; inputs[f.name] = input;
    el.append(h("label", { class: "lbl", for: input.id }, f.label), input, f.hint ? h("div", { class: "hint" }, f.hint) : null);
  }
  return { el, inputs, values: () => Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, v.value])) };
}

/* ---------- a light that follows the pointer across glass ---------- */
(function pointerLight() {
  let frame = 0, last = null;
  document.addEventListener("pointermove", (event) => {
    last = event;
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const target = last.target.closest && last.target.closest(".glass");
      if (!target) return;
      const box = target.getBoundingClientRect();
      target.style.setProperty("--mx", `${last.clientX - box.left}px`);
      target.style.setProperty("--my", `${last.clientY - box.top}px`);
    });
  }, { passive: true });
})();
