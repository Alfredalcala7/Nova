// Nova account PROTOTYPE. Everything runs in this browser only and nothing is sent anywhere.
// This is NOT real security: a real system must check passwords and send email from a server.
(() => {
  const $ = (id) => document.getElementById(id);
  const ACCOUNTS = "nova_prototype_accounts", SESSION = "nova_prototype_session";
  const CODE_MINUTES = 10, MAX_CODE_TRIES = 5, RESEND_SECONDS = 30, MAX_LOGIN_TRIES = 5, LOCK_SECONDS = 30;
  const VIEWS = ["signup", "verify", "login", "forgot", "reset", "profile", "account"];
  const LABELS = { fullName: "Full name", role: "Role", gender: "Gender", level: "Education level", strand: "Strand",
    grade: "Grade level", course: "Course", year: "Year level", major: "Major", subjects: "Subjects taught", taught: "Level taught" };
  const FIELD_IDS = { fullName: "pf-name", role: "role", gender: "gender", level: "level", strand: "strand", grade: "grade",
    course: "course", year: "year", major: "major", subjects: "subjects", taught: "taught" };

  let pending = null;      // the current code request, kept in memory only: { email, purpose, code, expires, tries, sentAt }
  let flowEmail = "";      // the email address used in the current sign-up, verify or reset step
  let inboxOn = false;
  const failures = {};     // login failures per email: { count, lockedUntil }

  const readAccounts = () => { try { return JSON.parse(localStorage.getItem(ACCOUNTS)) || {}; } catch { return {}; } };
  const writeAccounts = (accounts) => { try { localStorage.setItem(ACCOUNTS, JSON.stringify(accounts)); } catch { say("This browser could not save the data."); } };
  const getSession = () => { try { return sessionStorage.getItem(SESSION); } catch { return null; } };
  const setSession = (email) => { try { if (email) sessionStorage.setItem(SESSION, email); else sessionStorage.removeItem(SESSION); } catch { /* ignore */ } };
  const normalize = (email) => email.trim().toLowerCase();
  const validEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  const toBase64 = (bytes) => btoa(String.fromCharCode(...bytes));
  const fromBase64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

  function say(text, good = false) {
    const box = $("msg");
    box.textContent = text;
    box.className = "msg " + (good ? "good" : "bad");
    box.hidden = !text;
  }

  function passwordProblem(password) {
    if (password.length < 8) return "Use at least 8 characters.";
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return "Use both letters and numbers.";
    return "";
  }

  // Passwords are never stored. Only a salted PBKDF2 hash is kept (a real server would do this on the server).
  async function hashPassword(password, salt) {
    const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 210000 }, material, 256);
    return toBase64(new Uint8Array(bits));
  }

  function sixDigitCode() {  // secure random, with no bias toward low numbers
    const limit = Math.floor(0x100000000 / 1000000) * 1000000, value = new Uint32Array(1);
    do { crypto.getRandomValues(value); } while (value[0] >= limit);
    return String(value[0] % 1000000).padStart(6, "0");
  }

  function sendCode(email, purpose) {
    const now = Date.now();
    if (pending && pending.email === email && pending.purpose === purpose && now - pending.sentAt < RESEND_SECONDS * 1000) {
      return `Please wait ${Math.ceil((RESEND_SECONDS * 1000 - (now - pending.sentAt)) / 1000)} seconds before asking for another code.`;
    }
    pending = { email, purpose, code: sixDigitCode(), expires: now + CODE_MINUTES * 60000, tries: 0, sentAt: now };
    $("inbox").textContent = `Demo inbox. A real system would EMAIL this code and never show it on the page. Your code: ${pending.code}`;
    inboxOn = true;
    return "";
  }

  function checkCode(email, purpose, entered) {
    if (!pending || pending.email !== email || pending.purpose !== purpose || Date.now() > pending.expires) {
      return "That code is not valid or has expired. Ask for a new one.";
    }
    if (pending.tries >= MAX_CODE_TRIES) return "Too many wrong tries. Ask for a new code.";
    pending.tries += 1;
    return entered.trim() === pending.code ? "" : "That code is not correct.";
  }

  function syncFields() {
    const role = $("role").value, level = $("level").value;
    document.querySelectorAll("[data-role]").forEach((el) => { el.hidden = el.dataset.role !== role; });
    document.querySelectorAll("[data-level]").forEach((el) => { el.hidden = !(role === "Student" && el.dataset.level === level); });
  }

  function renderAccount() {
    const email = getSession(), account = email && readAccounts()[email], list = $("summary");
    list.replaceChildren();
    if (!account) return;
    const rows = [["Email", email]];
    Object.entries(account.profile || {}).forEach(([key, value]) => { if (value) rows.push([LABELS[key] || key, value]); });
    rows.forEach(([label, value]) => {
      const term = document.createElement("dt"), detail = document.createElement("dd");
      term.textContent = label;       // textContent, never innerHTML, so typed text can never run as code
      detail.textContent = value;
      list.append(term, detail);
    });
  }

  function show(name, message = "", good = false) {
    VIEWS.forEach((view) => { $("view-" + view).hidden = view !== name; });
    $("inbox").hidden = !(inboxOn && (name === "verify" || name === "reset"));
    say(message, good);
    if (name === "profile") syncFields();
    if (name === "account") renderAccount();
    const first = $("view-" + name).querySelector("input, select");
    if (first) first.focus();
  }

  // ---- form handlers --------------------------------------------------------------------

  $("form-signup").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = normalize($("su-email").value), password = $("su-pass").value;
    if (!validEmail(email)) return say("Enter a valid email address.");
    if (passwordProblem(password)) return say(passwordProblem(password));
    if (password !== $("su-pass2").value) return say("The passwords do not match.");
    const accounts = readAccounts();
    flowEmail = email;
    inboxOn = false;
    pending = null;
    if (!accounts[email]) {
      const salt = crypto.getRandomValues(new Uint8Array(16));
      accounts[email] = { salt: toBase64(salt), hash: await hashPassword(password, salt), verified: false, profile: null };
      writeAccounts(accounts);
      sendCode(email, "verify");
    } else {  // never confirm that an email already has an account
      $("inbox").textContent = "Demo inbox. This email already has an account, so a real system would email its owner instead of sending a code.";
      inboxOn = true;
    }
    show("verify", "If this email can be registered, a code was sent. Check the demo inbox.", true);
  });

  $("form-verify").addEventListener("submit", (event) => {
    event.preventDefault();
    const problem = checkCode(flowEmail, "verify", $("ver-code").value);
    if (problem) return say(problem);
    pending = null;
    inboxOn = false;
    const accounts = readAccounts();
    accounts[flowEmail].verified = true;
    writeAccounts(accounts);
    setSession(flowEmail);
    show("profile", "Email verified (demo). Now tell us about yourself.", true);
  });

  $("form-login").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = normalize($("li-email").value), password = $("li-pass").value;
    const record = failures[email] || (failures[email] = { count: 0, lockedUntil: 0 });
    if (Date.now() < record.lockedUntil) return say(`Too many tries. Wait ${Math.ceil((record.lockedUntil - Date.now()) / 1000)} seconds.`);
    const account = readAccounts()[email];
    const correct = account && (await hashPassword(password, fromBase64(account.salt))) === account.hash;
    if (!correct) {
      record.count += 1;
      if (record.count >= MAX_LOGIN_TRIES) { record.lockedUntil = Date.now() + LOCK_SECONDS * 1000; record.count = 0; }
      return say("The email or password is incorrect.");  // the same message whether or not the email exists
    }
    record.count = 0;
    flowEmail = email;
    if (!account.verified) {
      const wait = sendCode(email, "verify");
      return show("verify", wait || "Please verify your email first.", !wait);
    }
    setSession(email);
    show(account.profile ? "account" : "profile");
  });

  $("form-forgot").addEventListener("submit", (event) => {
    event.preventDefault();
    const email = normalize($("fg-email").value);
    if (!validEmail(email)) return say("Enter a valid email address.");
    flowEmail = email;
    inboxOn = false;
    pending = null;
    if (readAccounts()[email]) sendCode(email, "reset");
    show("reset", "If that email has an account, a reset code was sent. Check the demo inbox.", true);  // same message either way
  });

  $("form-reset").addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = $("rs-pass").value;
    if (passwordProblem(password)) return say(passwordProblem(password));
    const problem = checkCode(flowEmail, "reset", $("rs-code").value);
    if (problem) return say(problem);
    const accounts = readAccounts(), salt = crypto.getRandomValues(new Uint8Array(16));
    accounts[flowEmail].salt = toBase64(salt);
    accounts[flowEmail].hash = await hashPassword(password, salt);
    writeAccounts(accounts);
    pending = null;  // a code can be used only once
    inboxOn = false;
    show("login", "Password changed (demo). You can log in now.", true);
  });

  $("form-profile").addEventListener("submit", (event) => {
    event.preventDefault();
    const email = getSession();
    if (!email) return show("login", "Please log in first.");
    const v = (id) => $(id).value.trim();
    const profile = { fullName: v("pf-name"), role: v("role"), gender: v("gender") };
    if (profile.fullName.length < 2) return say("Enter your full name (at least 2 characters).");
    if (!profile.role) return say("Choose whether you are a student, a teacher, or another kind of user.");
    if (profile.role === "Student") {
      profile.level = v("level");
      if (!profile.level) return say("Choose your education level.");
      if (profile.level === "Senior high school") {
        Object.assign(profile, { strand: v("strand"), grade: v("grade") });
        if (!profile.strand || !profile.grade) return say("Choose your strand and grade level.");
      } else {
        Object.assign(profile, { course: v("course"), year: v("year"), major: v("major") });
        if (!profile.course || !profile.year) return say("Enter your course and choose your year level.");
      }
    } else if (profile.role === "Teacher") {
      Object.assign(profile, { subjects: v("subjects"), taught: v("taught") });
      if (!profile.subjects || !profile.taught) return say("Enter the subjects you teach and the level you teach.");
    }
    const accounts = readAccounts();
    accounts[email].profile = profile;
    writeAccounts(accounts);
    show("account", "Profile saved (in this browser only).", true);
  });

  // ---- buttons --------------------------------------------------------------------------

  $("role").addEventListener("change", syncFields);
  $("level").addEventListener("change", syncFields);
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => show(button.dataset.go)));

  function resend(purpose) {
    if (purpose === "reset" && !readAccounts()[flowEmail]) return say("If that email has an account, a new code was sent.", true);
    const wait = sendCode(flowEmail, purpose);
    show(purpose === "reset" ? "reset" : "verify", wait || "A new code was sent. Check the demo inbox.", !wait);
  }
  $("resend").addEventListener("click", () => resend("verify"));
  $("resend-reset").addEventListener("click", () => resend("reset"));

  $("edit-profile").addEventListener("click", () => {
    const account = readAccounts()[getSession()];
    Object.entries((account && account.profile) || {}).forEach(([key, value]) => { if (FIELD_IDS[key]) $(FIELD_IDS[key]).value = value; });
    show("profile");
  });
  $("logout").addEventListener("click", () => { setSession(null); show("login", "You are logged out.", true); });
  $("delete-account").addEventListener("click", () => {
    if (!confirm("Delete this prototype account from this browser?")) return;
    const accounts = readAccounts();
    delete accounts[getSession()];
    writeAccounts(accounts);
    setSession(null);
    show("signup", "The prototype account was deleted.", true);
  });

  // ---- start ----------------------------------------------------------------------------

  if (!(window.crypto && crypto.subtle)) {
    say("This prototype needs a secure browser context. Open it from the site folder or a local server.");
  } else {
    const email = getSession();
    show(email && readAccounts()[email] ? "account" : "signup");
  }
})();