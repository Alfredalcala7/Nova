"use strict";
/* Every screen except the AI chat. Each view(root) draws into the scrolling area. */

const STATUS = { not_started: "Not started", reviewed: "Reviewed", completed: "Completed" };
const STATUS_CLASS = { not_started: "", reviewed: "blue", completed: "green" };
const page = (title, sub, actions, ...kids) => h("div", { class: "page" }, h("div", { class: "page-head" }, h("div", {}, h("h2", {}, title), sub ? h("p", {}, sub) : null), actions ? h("div", { class: "actions" }, actions) : null), ...kids);
const empty = (title, text, button) => h("div", { class: "empty" }, h("strong", {}, title), text, button || null);
async function loadSamples() {
  try { await api("add_sample_content"); toast("Sample loaded", "Try the sample quiz now."); } catch { /* already loaded: just show it */ }
  const all = (await run("list_subjects")).data || [], sample = all.find((x) => x.name.startsWith("Sample"));
  if (!sample) return false;
  quizPick.subject = sample.id; quizPick.topic = ""; return true;
}
const subjectOptions = (subjects) => subjects.map((s) => ({ value: s.id, label: s.name }));

/* ================= Dashboard ================= */
async function viewDashboard(root) {
  const { ok, data: d } = await run("dashboard"); if (!ok) return;
  const name = d.first_name;
  const nothing = !d.counts.subjects;
  const tile = (n, label, ic, cls) => h("div", { class: "tile glass " + (cls || "") }, h("div", { class: "num", "data-n": n }, "0"), h("div", { class: "lab" }, icon(ic), label));
  const page_ = page("", "", null,
    h("section", { class: "hero glass" }, h("div", {},
      h("h2", {}, `${greeting()}${name ? ", " + name : ""}.`),
      h("p", {}, nothing ? "Welcome to Nova. Add a subject, try the sample quiz, or ask Nova AI to turn your notes into practice questions."
        : d.task_summary.overdue ? `You have ${plural(d.task_summary.overdue, "overdue task")}. A small start today beats a big start someday.`
        : d.task_summary.pending ? `${plural(d.task_summary.pending, "task")} coming up. Here is where you stand.` : "Nothing is due. A good moment to practice with a quiz.")),
      h("div", { class: "actions" }, h("button", { class: "btn btn-primary", onclick: () => go("ai") }, icon("sparkles"), "Ask Nova AI"), h("button", { class: "btn", onclick: () => go("quizzes") }, icon("play"), "Start a quiz"))),
    h("div", { class: "grid g4" }, tile(d.counts.subjects, "Subjects", "book"), tile(d.counts.topics_done + "/" + d.counts.topics, "Topics completed", "check"), tile(d.task_summary.pending, "Tasks pending", "calendar"), tile(d.task_summary.overdue, "Overdue", "alert", d.task_summary.overdue ? "warn" : "")),
    d.review_count ? h("div", { class: "card glass", style: { marginTop: "16px", display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" } }, icon("bulb"), h("div", { class: "grow", style: { flex: 1 } }, h("h3", {}, `${plural(d.review_count, "topic")} worth reviewing`), h("div", { class: "sub" }, `Your recent answers fell below ${d.threshold}%.`)), h("button", { class: "btn btn-sm", onclick: () => go("progress") }, "See why")) : null,
    h("div", { class: "grid g2", style: { marginTop: "16px" } },
      h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "Up next"), h("button", { class: "btn btn-sm", onclick: () => go("planner") }, "Planner")),
        d.upcoming.length ? h("div", { class: "list" }, d.upcoming.map((t) => h("div", { class: "item" }, h("div", { class: "grow" }, h("div", { class: "t" }, t.title), h("div", { class: "s" }, t.subject_name)), h("span", { class: "chip " + (t.label.startsWith("Overdue") ? "red" : "blue") }, t.label))))
          : empty("All clear", "No pending tasks.", h("button", { class: "btn btn-sm", onclick: () => go("planner") }, icon("plus"), "Add a task"))),
      h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "Recent quizzes"), h("button", { class: "btn btn-sm", onclick: () => go("progress") }, "Progress")),
        d.recent_quizzes.length ? h("div", { class: "list" }, d.recent_quizzes.map((q) => h("div", { class: "item" }, h("div", { class: "ring", style: { "--p": q.percent, "--c": q.percent >= d.threshold ? "var(--green)" : "var(--red)" } }, Math.round(q.percent)), h("div", { class: "grow" }, h("div", { class: "t" }, q.subject_name), h("div", { class: "s" }, `${q.topic_name} · ${q.when}`)), h("span", { class: "chip" }, `${q.score}/${q.total}`))))
          : empty("No quizzes yet", nothing ? "Load a ready-made sample to try one." : "Take one to start tracking progress.", nothing ? h("button", { class: "btn btn-sm", onclick: async () => { if (await loadSamples()) go("quizzes"); } }, icon("plus"), "Load sample questions") : h("button", { class: "btn btn-sm", onclick: () => go("quizzes") }, "Start a quiz")))));
  root.replaceChildren(page_);
  $$(".num[data-n]", page_).forEach((el) => {   // count up
    const text = String(el.dataset.n), parts = text.split("/"), target = Number(parts[0]); let start = null;
    const tick = (time) => { start ??= time; const p = Math.min(1, (time - start) / 700); const v = Math.round(target * (1 - Math.pow(1 - p, 3))); el.textContent = parts.length > 1 ? `${v}/${parts[1]}` : v; if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}

/* ================= My Subjects ================= */
let chosenSubject = null;
async function viewSubjects(root) {
  const { ok, data: subjects } = await run("list_subjects"); if (!ok) return;
  if (!subjects.find((s) => s.id === chosenSubject)) chosenSubject = subjects[0]?.id ?? null;
  const subject = subjects.find((s) => s.id === chosenSubject);
  const topics = subject ? (await run("list_topics", subject.id)).data || [] : [];
  const refresh = () => viewSubjects(root);

  const subjectDialog = async (existing) => {
    const f = buildForm([{ name: "name", label: "Subject name", value: existing?.name || "", max: 80 }, { name: "description", label: "Description (optional)", type: "textarea", value: existing?.description || "", max: 300 }]);
    await openSheet({ title: existing ? "Edit subject" : "New subject", body: f.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => {
      const v = f.values(); if (existing) await api("update_subject", existing.id, v.name, v.description); else chosenSubject = await api("add_subject", v.name, v.description); refresh(); } }] });
  };
  const deleteSubject = async () => {
    const n = (await run("count_subject_contents", subject.id)).data || {};
    const extra = Object.values(n).some(Boolean) ? ` This also deletes ${Object.entries(n).filter(([, v]) => v).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ")}.` : "";
    if (await confirmBox(`Delete "${subject.name}"?`, "This cannot be undone." + extra)) { if ((await run("delete_subject", subject.id)).ok) refresh(); }
  };
  const topicBox = h("input", { class: "field", placeholder: "Add a topic and press Enter", maxlength: 80, "aria-label": "New topic" });
  topicBox.addEventListener("keydown", async (e) => { if (e.key === "Enter" && topicBox.value.trim()) { if ((await run("add_topic", subject.id, topicBox.value)).ok) refresh(); } });

  root.replaceChildren(page("My Subjects", "Organize what you study and track each topic.", h("button", { class: "btn btn-primary", onclick: () => subjectDialog() }, icon("plus"), "New subject"),
    subjects.length ? h("div", { class: "split" },
      h("section", { class: "card glass" }, h("div", { class: "list" }, subjects.map((s) => h("div", { class: "item clickable" + (s.id === chosenSubject ? " selected" : ""), onclick: () => { chosenSubject = s.id; refresh(); } },
        h("div", { class: "grow" }, h("div", { class: "t" }, s.name), h("div", { class: "s" }, `${s.completed_count}/${s.topic_count} topics done`)), h("div", { class: "bar", style: { width: "56px" } }, h("i", { style: { width: s.topic_count ? `${100 * s.completed_count / s.topic_count}%` : "0%" } })))))),
      h("section", { class: "card glass" }, h("header", {}, h("div", {}, h("h3", {}, subject.name), subject.description ? h("div", { class: "sub" }, subject.description) : null),
        h("span", { style: { marginLeft: "auto", display: "flex", gap: "8px" } }, h("button", { class: "btn btn-sm", onclick: () => subjectDialog(subject) }, icon("edit"), "Edit"), h("button", { class: "btn btn-sm btn-danger", onclick: deleteSubject }, icon("trash"), "Delete"))),
        topicBox, h("div", { class: "list", style: { marginTop: "12px" } }, topics.length ? topics.map((t) => h("div", { class: "item" }, h("div", { class: "grow t" }, t.name),
          h("select", { class: "select", style: { width: "auto", padding: "6px 34px 6px 14px", borderRadius: "99px" }, "aria-label": `Status of ${t.name}`, onchange: async (e) => { if (!(await run("set_topic_status", t.id, e.target.value)).ok) refresh(); } }, Object.entries(STATUS).map(([k, v]) => h("option", { value: k, selected: k === t.status }, v))),
          h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": `Rename ${t.name}`, onclick: async () => { const f = buildForm([{ name: "name", label: "Topic name", value: t.name, max: 80 }]); await openSheet({ title: "Rename topic", body: f.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => { await api("update_topic", t.id, f.values().name); refresh(); } }] }); } }, icon("edit")),
          h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": `Delete ${t.name}`, onclick: async () => { const n = (await run("count_topic_questions", t.id)).data || 0; if (await confirmBox(`Delete "${t.name}"?`, n ? `Its ${plural(n, "question")} will be deleted too.` : "This cannot be undone.")) { if ((await run("delete_topic", t.id)).ok) refresh(); } } }, icon("trash"))))
          : [empty("No topics yet", "Type one above to get started.")])))
      : h("section", { class: "card glass" }, empty("No subjects yet", "A subject is something you study, like Biology or Programming.", h("button", { class: "btn btn-primary", onclick: () => subjectDialog() }, icon("plus"), "Add your first subject")))));
}

/* ================= Study Planner ================= */
async function viewPlanner(root) {
  const [t, s] = await Promise.all([run("tasks_overview"), run("list_subjects")]); if (!t.ok || !s.ok) return;
  const { groups, summary } = t.data, subjects = s.data, refresh = () => viewPlanner(root);
  const taskDialog = async (task) => {
    if (!subjects.length) { toast("Add a subject first", "Tasks belong to a subject.", "bad"); return; }
    const f = buildForm([{ name: "subject", label: "Subject", type: "select", options: subjectOptions(subjects), value: task?.subject_id ?? chosenSubject ?? subjects[0].id }, { name: "title", label: "What do you need to do?", value: task?.title || "", max: 100 },
      { name: "due", label: "Due date", type: "date", value: task?.due_date || new Date(Date.now() + 864e5).toLocaleDateString("en-CA") }, { name: "description", label: "Notes (optional)", type: "textarea", value: task?.description || "" }]);
    await openSheet({ title: task ? "Edit task" : "New task", body: f.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => { const v = f.values(); if (task) await api("update_task", task.id, Number(v.subject), v.title, v.description, v.due); else await api("add_task", Number(v.subject), v.title, v.description, v.due); refresh(); } }] });
  };
  const row = (task) => h("div", { class: "item" + (task.is_completed ? " done" : "") },
    h("button", { class: "check" + (task.is_completed ? " on" : ""), role: "checkbox", "aria-checked": String(!!task.is_completed), "aria-label": `Mark ${task.title} ${task.is_completed ? "not done" : "done"}`, onclick: async () => { if ((await run("set_task_completed", task.id, !task.is_completed)).ok) refresh(); } }, icon("check")),
    h("div", { class: "grow" }, h("div", { class: "t" }, task.title), h("div", { class: "s" }, [task.subject_name, task.description].filter(Boolean).join(" · "))),
    h("span", { class: "chip " + (task.is_completed ? "" : task.label.startsWith("Overdue") ? "red" : "blue") }, task.is_completed ? "Done" : task.label),
    h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Edit", onclick: () => taskDialog(task) }, icon("edit")),
    h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Delete", onclick: async () => { if (await confirmBox("Delete this task?", task.title)) { if ((await run("delete_task", task.id)).ok) refresh(); } } }, icon("trash")));
  const group = (label, list, tone) => list.length ? h("section", { class: "card glass", style: { marginBottom: "16px" } }, h("header", {}, h("h3", { style: tone ? { color: "var(--red)" } : {} }, label), h("span", { class: "chip" }, list.length)), h("div", { class: "list" }, list.map(row))) : null;
  const total = groups.overdue.length + groups.upcoming.length + groups.completed.length;
  root.replaceChildren(page("Study Planner", `${summary.pending} pending · ${summary.overdue} overdue · ${summary.completed} done`, h("button", { class: "btn btn-primary", onclick: () => taskDialog() }, icon("plus"), "New task"),
    total ? [group("Overdue", groups.overdue, true), group("Upcoming", groups.upcoming), group("Completed", groups.completed)]
      : h("section", { class: "card glass" }, empty("Nothing planned yet", "Add a task with a due date and Nova will keep track.", h("button", { class: "btn btn-primary", onclick: () => taskDialog() }, icon("plus"), "Add a task")))));
}

/* ================= Practice Quizzes ================= */
let quizPick = { subject: null, topic: "" };
async function viewQuizzes(root) {
  const { ok, data: subjects } = await run("list_subjects"); if (!ok) return;
  if (!subjects.find((s) => s.id === quizPick.subject)) quizPick = { subject: subjects[0]?.id ?? null, topic: "" };
  const topics = quizPick.subject ? (await run("list_topics", quizPick.subject)).data || [] : [];
  const questions = quizPick.subject ? (await run("questions", quizPick.subject, quizPick.topic ? Number(quizPick.topic) : null)).data || [] : [];
  const refresh = () => viewQuizzes(root);
  const subjectSel = h("select", { class: "select", "aria-label": "Subject", onchange: (e) => { quizPick = { subject: Number(e.target.value), topic: "" }; refresh(); } }, subjects.map((s) => h("option", { value: s.id, selected: s.id === quizPick.subject }, s.name)));
  const topicSel = h("select", { class: "select", "aria-label": "Topic", onchange: (e) => { quizPick.topic = e.target.value; refresh(); } }, h("option", { value: "" }, "All topics"), topics.map((t) => h("option", { value: t.id, selected: String(t.id) === String(quizPick.topic) }, t.name)));
  const start = async () => { const r = await run("quiz_start", quizPick.subject, quizPick.topic ? Number(quizPick.topic) : null); if (r.ok) runQuiz(root, r.data, refresh); };
  const questionDialog = async (q) => {
    if (!topics.length) { toast("Add a topic first", "Questions belong to a topic. Add one in My Subjects.", "bad"); return; }
    const f = buildForm([{ name: "topic", label: "Topic", type: "select", options: subjectOptions(topics), value: q?.topic_id ?? (quizPick.topic || topics[0].id) }, { name: "text", label: "Question", type: "textarea", value: q?.question_text || "" },
      ...[1, 2, 3, 4].map((n) => ({ name: "c" + n, label: `Choice ${"ABCD"[n - 1]}`, value: q ? q["choice_" + n] : "", max: 200 })), { name: "correct", label: "Correct answer", type: "select", options: [1, 2, 3, 4].map((n) => ({ value: n, label: "ABCD"[n - 1] })), value: q?.correct_choice ?? 1 }]);
    await openSheet({ title: q ? "Edit question" : "New question", wide: true, body: f.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => { const v = f.values(), c = [v.c1, v.c2, v.c3, v.c4];
      if (q) await api("update_question", q.id, Number(v.topic), v.text, c, Number(v.correct)); else await api("add_question", Number(v.topic), v.text, c, Number(v.correct)); refresh(); } }] });
  };
  root.replaceChildren(page("Practice Quizzes", "Test yourself. No answers are shown until you finish.", h("button", { class: "btn", onclick: () => { S.prefill = { text: "", mode: "chat" }; go("ai"); } }, icon("sparkles"), "Quiz from a file"),
    subjects.length ? [
      h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "Start a quiz")), h("div", { class: "form-row" }, h("div", {}, h("label", { class: "lbl", style: { marginTop: 0 } }, "Subject"), subjectSel), h("div", {}, h("label", { class: "lbl", style: { marginTop: 0 } }, "Topic"), topicSel)),
        h("div", { class: "row-gap", style: { marginTop: "18px" } }, h("button", { class: "btn btn-primary", disabled: !questions.length, onclick: start }, icon("play"), questions.length ? `Start (up to 10 of ${questions.length})` : "No questions yet"), h("span", { class: "hint" }, "Questions are picked at random."))),
      h("section", { class: "card glass", style: { marginTop: "16px" } }, h("header", {}, h("h3", {}, "Your questions"), h("button", { class: "btn btn-sm", onclick: () => questionDialog() }, icon("plus"), "Add question")),
        questions.length ? h("div", { class: "list" }, questions.map((q) => h("div", { class: "item" }, h("div", { class: "grow" }, h("div", { class: "t" }, q.question_text), h("div", { class: "s" }, `${q.topic_name}${q.is_sample ? " · sample" : ""}${q.explanation ? " · has explanation" : ""}`)),
          h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Edit question", onclick: () => questionDialog(q) }, icon("edit")),
          h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Delete question", onclick: async () => { if (await confirmBox("Delete this question?", q.question_text)) { if ((await run("delete_question", q.id)).ok) refresh(); } } }, icon("trash")))))
          : empty("No questions here", "Write your own, or let Nova AI make some from your notes.", h("div", { class: "row-gap", style: { justifyContent: "center" } }, h("button", { class: "btn btn-sm", onclick: () => questionDialog() }, icon("plus"), "Write one"), h("button", { class: "btn btn-sm", onclick: async () => { if (await loadSamples()) refresh(); } }, "Load samples"))))]
      : h("section", { class: "card glass" }, empty("Add a subject first", "Quizzes belong to a subject and topic.", h("div", { class: "row-gap", style: { justifyContent: "center" } }, h("button", { class: "btn btn-primary", onclick: () => go("subjects") }, "Add a subject"), h("button", { class: "btn", onclick: async () => { if (await loadSamples()) refresh(); } }, "Load sample questions"))))));
}
function runQuiz(root, questions, back) {
  const answers = {}; let i = 0;
  const draw = () => {
    const q = questions[i], last = i === questions.length - 1;
    const next = h("button", { class: "btn btn-primary", disabled: !answers[q.id], onclick: async () => { if (!last) { i++; draw(); return; }
      const r = await run("quiz_finish", q.subject_id ?? quizPick.subject, quizPick.topic ? Number(quizPick.topic) : null, questions, answers); if (r.ok) results(r.data); } }, last ? "Finish" : "Next");
    root.replaceChildren(h("div", { class: "page" }, h("div", { class: "quiz" },
      h("div", { class: "row-gap", style: { justifyContent: "space-between" } }, h("button", { class: "btn btn-sm btn-ghost", onclick: async () => { if (await confirmBox("Leave this quiz?", "Your answers will not be saved.", "Leave")) back(); } }, "Quit"), h("span", { class: "chip blue" }, `Question ${i + 1} of ${questions.length}`)),
      h("div", { class: "bar", style: { margin: "14px 0" } }, h("i", { style: { width: `${100 * (i + 1) / questions.length}%` } })),
      h("div", { class: "q-text" }, q.question_text), h("div", { class: "choices" }, q.choices.map((c, n) => h("button", { class: "choice" + (answers[q.id] === n + 1 ? " picked" : ""), type: "button", onclick: () => { answers[q.id] = n + 1; draw(); } }, h("span", { class: "k" }, "ABCD"[n]), h("span", {}, c)))),
      h("div", { class: "row-gap", style: { justifyContent: "space-between", marginTop: "22px" } }, h("button", { class: "btn", disabled: i === 0, onclick: () => { i--; draw(); } }, "Back"), next))));
  };
  const results = (r) => {
    const p = Math.round(100 * r.score / r.total);
    root.replaceChildren(h("div", { class: "page" }, h("div", { class: "quiz" }, h("section", { class: "card glass", style: { textAlign: "center" } }, h("div", { class: "score-big" }, `${r.score}/${r.total}`), h("p", { class: "sub" }, `${p}% correct. Saved to My Progress.`), h("div", { class: "row-gap", style: { justifyContent: "center", marginTop: "16px" } }, h("button", { class: "btn btn-primary", onclick: back }, "Done"), h("button", { class: "btn", onclick: () => go("progress") }, "My Progress"))),
      h("section", { class: "card glass", style: { marginTop: "16px" } }, h("h3", {}, "Review"), r.items.map((it) => h("div", { class: "review-q" }, h("div", { class: "t", style: { fontWeight: 650, color: "var(--ink)" } }, it.question_text),
        h("div", { class: "row-gap", style: { margin: "6px 0" } }, h("span", { class: "chip " + (it.is_correct ? "green" : "red") }, it.is_correct ? "Correct" : "Missed"), h("span", { class: "s", style: { color: "var(--muted)" } }, `You chose ${"ABCD"[it.chosen - 1]}: ${it["choice_" + it.chosen]}`)),
        it.is_correct ? null : h("div", { class: "s", style: { color: "var(--green)", fontWeight: 600 } }, `Correct: ${"ABCD"[it.correct_choice - 1]}: ${it["choice_" + it.correct_choice]}`), it.explanation ? h("div", { class: "why" }, it.explanation) : null))))));
  };
  draw();
}

/* ================= My Progress ================= */
async function viewProgress(root) {
  const { ok, data: p } = await run("progress"); if (!ok) return;
  const refresh = () => viewProgress(root);
  const stat = (n, l) => h("div", { class: "tile glass" }, h("div", { class: "num" }, n), h("div", { class: "lab" }, l));
  root.replaceChildren(page("My Progress", "A plain, visible rule: topics below your threshold are suggested for review.", null,
    h("div", { class: "grid g4" }, stat(p.attempts, "Quizzes taken"), stat(p.average == null ? "-" : pct(p.average), p.average == null ? "Average (after 3 quizzes)" : "Average score"), stat(p.recommendations.items.length, "Topics to review"),
      h("div", { class: "tile glass" }, h("div", { class: "lab", style: { marginTop: 0 } }, "Review threshold"), h("div", { class: "num", style: { fontSize: "1.9rem", margin: "6px 0" } }, p.threshold + "%"),
        h("input", { type: "range", min: 50, max: 90, step: 5, value: p.threshold, "aria-label": "Review threshold", onchange: async (e) => { if ((await run("set_review_threshold", Number(e.target.value))).ok) refresh(); } }))),
    h("div", { class: "grid g2", style: { marginTop: "16px" } },
      h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "Review suggestions")),
        p.recommendations.items.length ? h("div", { class: "list" }, p.recommendations.items.map((r) => h("div", { class: "item" }, h("div", { class: "grow" }, h("div", { class: "t" }, `${r.subject_name}: ${r.topic_name}`), h("div", { class: "s" }, r.reason)), h("span", { class: "chip red" }, pct(r.percent)))))
          : empty("Nothing to review", p.recommendations.judged_topics ? "Every judged topic is above your threshold." : "A topic needs at least 3 answered questions before Nova judges it.")),
      h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "By subject")),
        p.subjects.length ? h("div", { class: "list" }, p.subjects.map((s) => h("div", { class: "item" }, h("div", { class: "grow" }, h("div", { class: "t" }, s.name), h("div", { class: "s" }, `${s.completed_count}/${s.topic_count} topics · ${plural(s.attempts, "quiz", "quizzes")}`), h("div", { class: "bar", style: { marginTop: "6px" } }, h("i", { style: { width: `${s.average || 0}%` } }))), h("span", { class: "chip" }, s.average == null ? "-" : pct(s.average))))) : empty("No subjects yet", ""))),
    h("section", { class: "card glass", style: { marginTop: "16px" } }, h("header", {}, h("h3", {}, "Quiz history")),
      p.history.length ? h("div", { class: "list" }, p.history.slice(0, 30).map((q) => h("div", { class: "item" }, h("div", { class: "ring", style: { "--p": q.percent, "--c": q.percent >= p.threshold ? "var(--green)" : "var(--red)" } }, Math.round(q.percent)), h("div", { class: "grow" }, h("div", { class: "t" }, q.subject_name), h("div", { class: "s" }, `${q.topic_name} · ${q.when}`)), h("span", { class: "chip" }, `${q.score}/${q.total}`)))) : empty("No quizzes yet", "Your results will appear here."))));
}

/* ================= Simple Terms ================= */
async function viewTerms(root) {
  let query = "";
  const results = h("div", { class: "list" });
  const search = h("input", { class: "field", placeholder: "Search terms...", "aria-label": "Search terms" });
  const aiBox = h("textarea", { class: "textarea", rows: 2, maxlength: 2000, placeholder: "Type any word or question, for example: What is recursion?" });
  const aiOut = h("div", { class: "ai-body", style: { marginTop: "12px" } });
  const load = async () => {
    const r = await run("list_terms", query); if (!r.ok) return;
    results.replaceChildren(...(r.data.length ? r.data.map((t) => h("div", { class: "item", style: { alignItems: "flex-start" } }, h("div", { class: "grow" }, h("div", { class: "t" }, t.term), h("div", { style: { marginTop: "2px" } }, t.explanation), t.example ? h("div", { class: "s", style: { marginTop: "6px" } }, "Example: " + t.example) : null),
      h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Edit", onclick: () => termDialog(t) }, icon("edit")), h("button", { class: "btn btn-ghost icon-btn btn-sm", "aria-label": "Delete", onclick: async () => { if (await confirmBox(`Delete "${t.term}"?`, "")) { await run("delete_term", t.id); load(); } } }, icon("trash"))))
      : [empty("No terms found", query ? "Try another word, or ask the AI helper." : "Load the starter list or add your own.", query ? null : h("button", { class: "btn btn-sm", onclick: async () => { await run("load_starter_terms"); load(); } }, "Load starter terms"))]));
  };
  const termDialog = async (t) => {
    const f = buildForm([{ name: "term", label: "Term", value: t?.term || "", max: 60 }, { name: "explanation", label: "Plain-language meaning", type: "textarea", value: t?.explanation || "" }, { name: "example", label: "Example (optional)", type: "textarea", value: t?.example || "", rows: 2 }]);
    await openSheet({ title: t ? "Edit term" : "New term", body: f.el, buttons: [{ label: "Cancel", kind: "quiet" }, { label: "Save", kind: "primary", run: async () => { const v = f.values(); if (t) await api("update_term", t.id, v.term, v.explanation, v.example); else await api("add_term", v.term, v.explanation, v.example); load(); } }] });
  };
  search.addEventListener("input", debounce(() => { query = search.value.trim(); load(); }, 200));
  const ask = h("button", { class: "btn btn-primary", onclick: async (e) => {
    const b = e.currentTarget; if (!aiBox.value.trim()) return; b.disabled = true; aiOut.textContent = "Thinking...";
    try { const text = await api("ai_explain", aiBox.value); aiOut.dataset.raw = text; renderAnswer(aiOut, text, false); } catch (err) { aiOut.replaceChildren(h("div", { class: "ai-error" }, err.message)); } b.disabled = false; } }, icon("sparkles"), "Explain simply");
  root.replaceChildren(page("Simple Terms", "Hard words in plain language. Works offline; the AI helper needs internet.", h("button", { class: "btn btn-primary", onclick: () => termDialog() }, icon("plus"), "New term"),
    h("section", { class: "card glass" }, h("header", {}, h("h3", {}, "Ask the AI helper")), aiBox, h("div", { class: "row-gap", style: { marginTop: "12px" } }, ask, h("button", { class: "btn", onclick: () => { S.prefill = { text: aiBox.value ? "Explain simply: " + aiBox.value : "Explain simply: ", mode: "explain" }; go("ai"); } }, "Continue in chat")), aiOut),
    h("section", { class: "card glass", style: { marginTop: "16px" } }, search, h("div", { style: { marginTop: "12px" } }, results))));
  load();
}

/* ================= Settings ================= */
async function viewSettings(root) {
  const { settings, choices, fonts, prefs } = S.all; const draft = { ...settings };
  const status = await api("ai_status").catch(() => ({}));
  const seg = (key, options, fmt = (v) => v) => h("div", { class: "seg" }, options.map((v) => h("button", { type: "button", "aria-pressed": String(draft[key] === v), onclick: (e) => { draft[key] = v; $$("button", e.currentTarget.parentElement).forEach((b) => b.setAttribute("aria-pressed", "false")); e.currentTarget.setAttribute("aria-pressed", "true"); preview(); } }, fmt(v))));
  const toggle = (key) => h("button", { class: "switch", role: "switch", "aria-checked": String(!!draft[key]), onclick: (e) => { draft[key] = draft[key] ? 0 : 1; e.currentTarget.setAttribute("aria-checked", String(!!draft[key])); } });
  const prefToggle = (key, onChange) => h("button", { class: "switch", role: "switch", "aria-checked": String(prefs[key] === "1"), onclick: async (e) => { prefs[key] = prefs[key] === "1" ? "0" : "1"; e.currentTarget.setAttribute("aria-checked", String(prefs[key] === "1")); await run("set_pref", key, prefs[key]); onChange && onChange(); applyLook(); } });
  const row = (t, s, control) => h("div", { class: "setting" }, h("div", { class: "grow" }, h("div", { class: "t" }, t), s ? h("div", { class: "s" }, s) : null), control);
  const color = (key) => h("input", { class: "field", type: "color", value: draft[key], style: { width: "80px" }, "aria-label": key, oninput: (e) => { draft[key] = e.target.value.toUpperCase(); preview(); } });
  const preview = () => { S.all.settings = { ...draft }; if (draft.theme_mode === "Custom") S.all.palette = customPalette(draft); applyLook(); };
  const custom = h("div", { class: "form-row", style: { marginTop: "12px" } }, ...[["custom_sidebar", "Sidebar / depth"], ["custom_accent", "Accent"], ["custom_background", "Background"]].map(([k, l]) => h("div", {}, h("label", { class: "lbl", style: { marginTop: 0 } }, l), color(k))));
  const modeSeg = seg("theme_mode", choices.theme_mode); modeSeg.addEventListener("click", () => { custom.hidden = draft.theme_mode !== "Custom"; }); custom.hidden = draft.theme_mode !== "Custom";
  const glass = h("input", { type: "range", min: 0, max: 100, value: prefs.ui_glass, "aria-label": "Glass blur", oninput: (e) => { prefs.ui_glass = e.target.value; applyLook(); }, onchange: (e) => run("set_pref", "ui_glass", e.target.value) });
  const keyBox = h("input", { class: "field", type: "password", placeholder: status.configured ? "Key saved. Paste a new one to replace it." : "Paste your API key", autocomplete: "off", "aria-label": "API key" });
  const providerSel = h("select", { class: "select", style: { width: "auto" }, "aria-label": "Provider" }, h("option", { value: "gemini" }, "Google Gemini (free option)"), h("option", { value: "anthropic" }, "Claude"));
  if (status.provider) providerSel.value = status.provider;

  root.replaceChildren(page("Settings", "Make Nova look and behave the way you like.", h("button", { class: "btn btn-primary", onclick: async () => { const r = await run("save_settings", draft); if (r.ok) { S.all = r.data; applyLook(); toast("Saved", "Your settings are saved."); } } }, icon("check"), "Save settings"),
    h("section", { class: "card glass" }, h("h3", {}, "Appearance"), row("Theme", "Light, dark, follow your computer, or your own colors.", modeSeg), custom,
      row("Text size", null, seg("text_scale", choices.text_scale, (v) => v + "%")), row("Zoom", "Makes everything larger or smaller.", seg("zoom", choices.zoom, (v) => v + "%")),
      row("Font", null, h("select", { class: "select", style: { width: "auto" }, onchange: (e) => { draft.font_family = e.target.value; preview(); } }, fonts.map((f) => h("option", { value: f, selected: f === draft.font_family }, f)))),
      row("Glass blur", "How frosted the glass looks.", h("div", { style: { width: "180px" } }, glass)),
      row("Reduce transparency", "Solid panels instead of glass. Easier on older computers.", prefToggle("ui_solid")), row("Moving background", "Turn off to stop the slow background drift.", prefToggle("ui_motion"))),
    h("section", { class: "card glass", style: { marginTop: "16px" } }, h("h3", {}, "AI connection"), h("p", { class: "sub", style: { marginBottom: "10px" } }, status.configured ? `Connected: ${status.provider} (${status.model}).` : "Not connected yet. The key stays on this computer and is sent only to the provider you pick."),
      h("div", { class: "row-gap" }, providerSel, h("div", { style: { flex: 1, minWidth: "220px" } }, keyBox), h("button", { class: "btn btn-primary", onclick: async () => { const r = await run("ai_save_key", providerSel.value, keyBox.value); if (r.ok) { keyBox.value = ""; toast("AI connected", r.data.configured ? `Using ${r.data.provider}.` : "Key removed."); refreshStatus(); viewSettings(root); } } }, "Save key")),
      h("p", { class: "hint" }, "Get a free Gemini key at aistudio.google.com. Leave the box empty and press Save to remove a saved key.")),
    h("section", { class: "card glass", style: { marginTop: "16px" } }, h("h3", {}, "Reminders"), row("Show task reminders", "A small message inside Nova when something is due.", toggle("notify_enabled")),
      row("Remind me about tasks due within", null, seg("notify_days", choices.notify_days, (v) => plural(v, "day"))), row("Include overdue tasks", null, toggle("notify_overdue")),
      row("Check again every", "Otherwise Nova checks only when it starts.", seg("notify_interval", choices.notify_interval, (v) => (v ? v + " min" : "Never"))),
      h("div", { style: { paddingTop: "10px" } }, h("button", { class: "btn btn-sm", onclick: async () => { const r = await run("reminder", draft.notify_days, draft.notify_overdue); if (r.ok) toast("Test reminder", r.data || "Nothing is due soon or overdue right now."); } }, "Send a test"))),
    h("section", { class: "card glass", style: { marginTop: "16px" } }, h("h3", {}, "Reset"), h("p", { class: "sub" }, "Puts appearance and reminders back to normal. Your subjects, quizzes and chats are not touched."),
      h("button", { class: "btn btn-danger btn-sm", style: { marginTop: "10px" }, onclick: async () => { if (await confirmBox("Reset settings?", "Appearance and reminders return to their defaults.", "Reset")) { const r = await run("reset_settings"); if (r.ok) { S.all = r.data; applyLook(); viewSettings(root); } } } }, "Reset settings"))));
}

/* ================= Account ================= */
async function viewAccount(root) {
  const { ok, data } = await run("get_profile"); if (!ok) return;
  const f = buildForm([{ name: "name", label: "Full name", value: data.profile.name, max: 80 }, { name: "role", label: "Role", type: "select", options: ["", ...data.roles], value: data.profile.role },
    { name: "school", label: "School or university", value: data.profile.school, max: 100 }, { name: "program", label: "Course, strand or subjects", value: data.profile.program, max: 100 },
    { name: "year", label: "Year or grade", value: data.profile.year, max: 40 }, { name: "goal", label: "Your study goal", type: "textarea", value: data.profile.goal, max: 300, hint: "Nova AI uses this to tailor its help. It stays on this computer except when you chat." }]);
  const picture = h("input", { type: "file", accept: "image/*", hidden: true, onchange: async (e) => { const file = e.target.files[0]; if (!file) return; if ((await run("save_avatar", file.name, await fileToBase64(file))).ok) { toast("Picture saved", ""); await refreshProfile(); viewAccount(root); } } });
  root.replaceChildren(page("Account", "Everything here is stored only on this computer.", h("button", { class: "btn btn-primary", onclick: async () => { if ((await run("save_profile", f.values())).ok) { toast("Saved", "Account saved."); await refreshProfile(); } } }, icon("check"), "Save"),
    h("div", { class: "split" }, h("section", { class: "card glass", style: { textAlign: "center" } }, h("div", { style: { width: "120px", height: "120px", margin: "0 auto 14px", fontSize: "2.6rem" } }, avatarNode(data.has_avatar ? `/api/avatar?t=${TOKEN}&v=${data.stamp}` : null, data.profile.name)),
        data.pictures ? [h("div", { class: "row-gap", style: { justifyContent: "center" } }, h("button", { class: "btn btn-sm", onclick: () => picture.click() }, icon("upload"), "Choose picture"), data.has_avatar ? h("button", { class: "btn btn-sm btn-ghost", onclick: async () => { await run("remove_avatar"); await refreshProfile(); viewAccount(root); } }, "Remove") : null), picture] : h("p", { class: "hint" }, data.pillow_help)),
      h("section", { class: "card glass" }, f.el))));
}
