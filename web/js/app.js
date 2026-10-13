"use strict";
/* The shell: menu, three-line button, routing, theme, reminders, and the heartbeat that lets Nova quit with its window. */

const S = { all: null, firstName: "", prefill: null, openThread: null };
const SCREENS = [
  { id: "dashboard", label: "Dashboard", icon: "home", view: viewDashboard },
  { id: "ai", label: "Nova AI", icon: "chat", view: viewChat },
  { id: "subjects", label: "My Subjects", icon: "book", view: viewSubjects },
  { id: "planner", label: "Study Planner", icon: "calendar", view: viewPlanner },
  { id: "quizzes", label: "Practice Quizzes", icon: "quiz", view: viewQuizzes },
  { id: "progress", label: "My Progress", icon: "chart", view: viewProgress },
  { id: "terms", label: "Simple Terms", icon: "bulb", view: viewTerms },
  { divider: true },
  { id: "settings", label: "Settings", icon: "sliders", view: viewSettings },
  { id: "account", label: "Account", icon: "user", view: viewAccount },
];
const appEl = $("#app"), viewEl = $("#view"), pill = h("div", { class: "nav-pill" });
const narrow = () => matchMedia("(max-width: 900px)").matches;
let current = null, serial = 0;

/* ---------- look and feel ---------- */
const lum = (hex) => { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; };
const shade = (hex, amt) => "#" + [1, 3, 5].map((i) => { const v = parseInt(hex.slice(i, i + 2), 16); return Math.round(amt < 0 ? v * (1 + amt) : v + (255 - v) * amt).toString(16).padStart(2, "0"); }).join("");
function customPalette(s) { return { IS_DARK: lum(s.custom_background) < .179, BLUE: s.custom_accent, BACKGROUND: s.custom_background, SIDEBAR: s.custom_sidebar, ON_ACCENT: lum(s.custom_accent) > .4 ? "#10151F" : "#FFFFFF", BLUE_HOVER: shade(s.custom_accent, lum(s.custom_accent) > .25 ? -.18 : .18) }; }
function applyLook() {
  const { settings, palette, prefs } = S.all, root = document.documentElement, custom = settings.theme_mode === "Custom" && palette;
  const dark = custom ? palette.IS_DARK : settings.theme_mode === "Dark" || (settings.theme_mode === "System" && matchMedia("(prefers-color-scheme: dark)").matches);
  root.dataset.theme = dark ? "dark" : "light";
  for (const [prop, value] of [["--accent", custom && palette.BLUE], ["--accent-2", custom && palette.BLUE_HOVER], ["--on-accent", custom && palette.ON_ACCENT], ["--bg", custom && palette.BACKGROUND], ["--navy", custom && palette.SIDEBAR]]) value ? root.style.setProperty(prop, value) : root.style.removeProperty(prop);
  root.style.setProperty("--font", `"${settings.font_family}", "Segoe UI Variable Display", system-ui, sans-serif`);
  root.style.fontSize = `${(16 * settings.text_scale / 100 * settings.zoom / 125).toFixed(2)}px`;
  root.style.setProperty("--blur", `${Math.round(10 + Number(prefs.ui_glass) * .34)}px`);
  root.classList.toggle("solid", prefs.ui_solid === "1"); root.classList.toggle("still", prefs.ui_motion === "0");
  root.classList.toggle("has-lens", !!window.chrome && prefs.ui_solid !== "1");
  $("#theme-toggle").replaceChildren(icon(dark ? "sun" : "moon"));
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => S.all && applyLook());
$("#theme-toggle").addEventListener("click", async () => {
  const dark = document.documentElement.dataset.theme === "dark", mode = dark ? "Light" : "Dark";
  const r = await run("save_settings", { ...S.all.settings, theme_mode: mode }); if (r.ok) { S.all = r.data; applyLook(); }
});

function avatarNode(url, name) {
  const initial = (name || "").trim()[0];
  return url ? h("img", { class: "avatar", src: url, alt: "" }) : h("div", { class: "avatar" }, initial ? initial.toUpperCase() : icon("user"));
}
async function refreshProfile() {
  const r = await run("get_profile"); if (!r.ok) return;
  S.firstName = (r.data.profile.name || "").split(" ")[0];
  $("#avatar-btn").replaceChildren(avatarNode(r.data.has_avatar ? `/api/avatar?t=${TOKEN}&v=${r.data.stamp}` : null, r.data.profile.name));
}
async function refreshStatus() {
  const s = await api("ai_status").catch(() => ({ configured: false }));
  const dot = $("#ai-dot"); dot.classList.toggle("on", !!s.configured); dot.title = s.configured ? `AI connected (${s.provider})` : "AI not connected. Open Settings to add a key.";
}

/* ---------- menu and the three-line button ---------- */
function setSidebar(open, save = true) {
  appEl.classList.toggle("collapsed", !open); $("#menu").setAttribute("aria-expanded", String(open));
  if (open) requestAnimationFrame(movePill);
  if (save && !narrow()) run("set_pref", "ui_sidebar", open ? "1" : "0");
}
$("#menu").addEventListener("click", () => setSidebar(appEl.classList.contains("collapsed")));
$("#scrim").addEventListener("click", () => setSidebar(false, false));
$("#avatar-btn").addEventListener("click", () => go("account"));

function buildNav() {
  const nav = $("#nav"); nav.replaceChildren(pill);
  for (const s of SCREENS) {
    if (s.divider) { nav.append(h("hr")); continue; }
    nav.append(h("a", { href: `#/${s.id}`, "data-id": s.id }, icon(s.icon), s.label));
  }
  $("#side-foot").replaceChildren(h("span", {}, "Nova 1.5 · Glass"));
}
function movePill() {
  const active = $('#nav a[aria-current="page"]'); if (!active) return;
  pill.style.height = active.offsetHeight + "px"; pill.style.transform = `translateY(${active.offsetTop}px)`;
}
new ResizeObserver(movePill).observe($("#nav"));

/* ---------- routing ---------- */
function go(id) { if (location.hash === `#/${id}`) render(); else location.hash = `#/${id}`; }
async function render() {
  const id = (location.hash.match(/^#\/(\w+)/) || [])[1] || "dashboard";
  const screen = SCREENS.find((s) => s.id === id) || SCREENS[0], mine = ++serial;
  if (current === "ai" && screen.id !== "ai" && Chat.abort) Chat.abort.abort();
  current = screen.id;
  $$("#nav a").forEach((a) => { if (a.dataset.id === screen.id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  movePill(); $("#title").textContent = screen.label;
  viewEl.classList.remove("fill"); viewEl.scrollTop = 0; viewEl.replaceChildren();
  if (narrow()) setSidebar(false, false);
  try { await screen.view(viewEl); } catch (error) { if (mine === serial) viewEl.replaceChildren(page("Something went wrong", "", null, h("section", { class: "card glass" }, empty("Nova could not show this screen", error.message)))); }
}
window.addEventListener("hashchange", render);

/* ---------- keyboard ---------- */
document.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) { if (e.key === "Escape" && narrow()) setSidebar(false, false); return; }
  if (e.key.toLowerCase() === "b") { e.preventDefault(); $("#menu").click(); }
  else if (e.key.toLowerCase() === "k") { e.preventDefault(); go("ai"); }
  else if (/^[1-9]$/.test(e.key)) { const s = SCREENS.filter((x) => x.id)[Number(e.key) - 1]; if (s) { e.preventDefault(); go(s.id); } }
});

/* ---------- reminders and heartbeat ---------- */
let reminderTimer = null;
async function checkReminders() {
  const { settings } = S.all; if (!settings.notify_enabled) return;
  const r = await api("reminder", settings.notify_days, settings.notify_overdue).catch(() => null);
  if (r) toast("Study reminder", r, "good", 9);
}
function scheduleReminders() {
  clearInterval(reminderTimer);
  const minutes = S.all.settings.notify_interval; if (minutes) reminderTimer = setInterval(checkReminders, minutes * 60000);
}
setInterval(() => post("/api/ping", {}).catch(() => {}), 4000);
addEventListener("pagehide", () => navigator.sendBeacon(`/api/bye?t=${TOKEN}`, new Blob(["{}"], { type: "text/plain" })));

/* ---------- start ---------- */
(async function start() {
  buildNav();
  try { S.all = await api("get_settings"); } catch (error) { viewEl.textContent = error.message; return; }
  applyLook();
  setSidebar(narrow() ? false : S.all.prefs.ui_sidebar === "1", false);
  await Promise.all([refreshProfile(), refreshStatus()]);
  await render();
  setTimeout(checkReminders, 1500); scheduleReminders();
})();
