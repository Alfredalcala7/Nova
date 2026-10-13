# Nova: a study planner, AI tutor and practice quiz app

**Version 1.5 "Glass"** is a full rebuild of the interface and the AI. The database and services from 1.0 are kept, so your saved data carries over.

- **Liquid glass design** (inspired by iOS 26) on both the app and the website: translucent panels, blur, soft highlights, light and dark themes, and your original navy and blue colors.
- **Hideable menu**: the three-line button (or Ctrl+B) hides and shows the left menu. It becomes a slide-over drawer on narrow windows, and Nova remembers your choice.
- **Nova AI chat**: answers stream as they are written, history is saved, and replies adapt to your level. Styles: Chat, Explain simply, Summarize, Step by step.
- **Files and photos in**: attach (button, drag and drop, or paste) PDFs, PowerPoint, Word, Excel, text files and pictures. Nova summarizes them.
- **Quizzes from your material**: turn any attachment into 5 to 15 multiple-choice questions with explanations, answer them in the chat, and save them to a subject.
- **Scrolling fixed**: the page itself never scrolls. Each screen scrolls inside its own box, the chat stays pinned to the newest message, and a "Latest" button appears when you scroll up.
- **Other**: date picker in the planner, quiz explanations, AI key saved from Settings, and 54 automated tests.

## Run it

```
py main.py
```

Needs only Python 3.10+. The window is a Microsoft Edge or Google Chrome app window (Windows has Edge already). If `pywebview` is installed Nova uses that for a native window instead. The old CustomTkinter version still runs with `py classic_main.py` (`pip install customtkinter`). Optional: `pip install Pillow` for account pictures.

Turn on the AI: Settings, then AI connection, paste a key (a free Gemini key from aistudio.google.com works). It is stored only in `%APPDATA%\Nova\ai_keys.json`. You can also use the `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` environment variables.

### How it fits together

`main.py` starts a small web server that listens only on `127.0.0.1` and opens the window. Every request needs a secret token that only the Nova window knows, so other programs and websites cannot talk to it. `api.py` connects the screens (`web/`) to the same services as before. The window tells the server when it closes, and the server then quits.

| New file | Job |
|---|---|
| `server.py`, `api.py` | Local server and the bridge to the services |
| `services/ai_service.py` | Chat, streaming, summaries, quiz generation, model fallback |
| `services/file_service.py` | Reads PDFs, images, Word, PowerPoint, Excel and text safely |
| `services/chat_service.py` | Saved chats (only names and extracted text are stored, never file bytes) |
| `web/` | The glass interface: `css/glass.css`, `css/app.css`, `js/*.js` |

AI privacy: messages and files you attach are sent to the provider you chose (Gemini or Claude) only when you send them, and Nova asks first. On Google's free plan the provider may use them to improve its products, so do not send personal information or private schoolwork. AI can be wrong.

## The problem

Students have more learning tools than ever, but many still lack a simple way to organize their studying, check what they actually know, and decide what to review next. Easy access to answers can also tempt students to collect answers instead of learning them, and technical words such as 'instantiate' can leave beginners confused. This is our framing of the problem, based on common student experience and concerns raised in UNESCO's 2023 education report. We do **not** claim that Nova has been proven to improve learning.

## Features

- **Dashboard:** counts of subjects, topics and tasks, upcoming deadlines, recent quiz results, progress bars, and a button to start a quiz. A guide appears when there is no data yet.
- **My Subjects:** add, edit and delete subjects and topics, and mark topics as Not started, Reviewed or Completed.
- **Study Planner:** tasks with a subject, due date and optional description, grouped as Overdue, Upcoming and Completed.
- **Practice Quizzes:** write your own multiple-choice questions, or load clearly labeled sample questions. A quiz uses up to 10 random questions, shows one at a time with no early answers, scores automatically, and ends with a review of the correct answers.
- **My Progress:** quiz history, an average score (shown after 3 quizzes), subject progress, and topics suggested for review with the reason for each.
- **Simple Terms:** a searchable list of programming terms (such as instantiate, class and inheritance) explained in plain language with examples, where you can add your own terms. It works offline. An **optional AI helper** on the same screen explains any term or question in simple words. It needs internet and your own free API key, AI can make mistakes, and what you type is sent to the AI provider.
- **Settings:** light, dark, system or custom colors (picked with the Windows color picker), font, text size, zoom (100% to 200%), start-maximized, and task reminders, with a Save button. Reminders appear inside Nova while it is open and are not Windows notifications.
- **Account:** your name, a few details about you, and an optional profile picture, all stored on this computer. Pictures need the optional Pillow package (`python -m pip install pillow`).
- **Keyboard shortcuts:** F11 full screen, Esc leaves it, Ctrl and +/- zoom, Ctrl and 0 resets zoom, Ctrl+1 to Ctrl+6 switch screens. Enter saves and Esc closes pop-up forms.

### How review suggestions work

Nova adds up your saved answers for each topic. A topic needs at least **3 answered questions** before it is judged. If the percentage correct is below the **review threshold** (70% to start; you can choose 50% to 90% on the My Progress screen), Nova suggests reviewing that topic and shows the numbers, for example "3 of 12 answers correct (25%), below your 70% review threshold." This is a simple, visible rule. It is not artificial intelligence, and the threshold is a starting point, not a definition of mastery.

## Technologies

| Part | Technology | Why |
|---|---|---|
| Language | Python 3 (developed on 3.14.7) | Beginner-friendly and well supported |
| Interface | CustomTkinter | Modern-looking desktop widgets, written in Python |
| Database | SQLite through Python's built-in `sqlite3` | Stores data on the student's computer, no server or account |
| Tests | `unittest` (built in) | No extra dependency |
| Optional AI helper | Google Gemini (has a free tier) or Claude, called with Python's built-in `urllib` | No extra package and no Nova server. The key stays on your computer |
| Website | HTML, CSS and a little JavaScript | The assignment asks for a campaign website |

The only dependency to install is CustomTkinter.

## Installation (Windows)

1. Install Python 3 from python.org.
2. Open PowerShell in the project folder (the folder containing `main.py`).
3. Create and activate a virtual environment, then install the dependency:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If activation says scripts are disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and try again.

4. Start Nova:

```powershell
python main.py
```

Nova saves its data in `%APPDATA%\Nova\nova.db`, so your data survives restarts and does not depend on where you start the app. To view the website, open `website/index.html` in a browser.

### Optional: the AI helper

Everything works without it. To turn it on, create a free API key in Google AI Studio (if it asks for payment details, stop) and set it for the current terminal, then start Nova from that terminal:

```powershell
$env:GEMINI_API_KEY = 'your-key'
python main.py
```

Never put the key in the code, on the website, or in a screenshot. Nova finds a working model for your key automatically. It limits questions to 2,000 characters and 30 requests per session. On Google's free plan, the text you send may be used by Google to improve its products, so never type personal information or private schoolwork. A shared copy of Nova must never contain your key. Sharing it widely would need a small server to hold the key.

## Project structure

```
Nova/
├── main.py                 starts the app
├── requirements.txt
├── database/
│   ├── schema.py           table definitions
│   └── db_manager.py       connection and first-run setup
├── services/               rules and database queries
│   ├── study_service.py    subjects and topics
│   ├── planner_service.py  tasks and deadlines
│   ├── quiz_service.py     questions, scoring, saved attempts
│   ├── progress_service.py history, averages, review suggestions
│   ├── dashboard_service.py
│   ├── glossary_service.py  Simple Terms
│   └── ai_service.py        optional AI helper
├── ui/                     everything the user sees
│   ├── app.py              window, sidebar, navigation
│   ├── components.py       shared buttons and pop-up form
│   ├── theme.py            colors and fonts
│   └── dashboard.py, subjects.py, planner.py, quizzes.py, progress.py, terms.py
├── tests/                  automated tests and a demo-data script
├── website/                the campaign website
└── TEST_CHECKLIST.md       manual test checklist
```

**How the layers work together:** a screen (`ui/`) never writes SQL. It calls a function in `services/`, which checks the input and talks to the database through `database/`. Each layer has one job, which makes problems easier to find and fix.

## Database

Eight tables, all created automatically on first run (running setup again never erases data):

| Table | Purpose |
|---|---|
| `subjects` | Name (unique, ignoring capitals) and description |
| `topics` | Belongs to a subject; status is Not started, Reviewed or Completed |
| `tasks` | Belongs to a subject; title, description, due date (YYYY-MM-DD), completed flag |
| `quiz_questions` | Belongs to a topic; question, four choices, number of the correct choice, sample flag |
| `quiz_attempts` | One finished quiz: subject, optional topic, score, total, time |
| `attempt_answers` | Each answer in an attempt: question, chosen choice, correct or not |
| `settings` | The review threshold |
| `glossary_terms` | Simple Terms: term, plain-language explanation, example, starter flag |

**Relationships:** subject → topics → questions, and subject → tasks and attempts. Foreign keys are enforced. Deleting a subject also deletes its topics, tasks, questions and quiz history, and the app asks for confirmation and lists exactly what will be removed. Deleting a topic or question keeps old quiz attempts but removes the link to it. All queries use parameters, which prevents SQL injection, and a finished quiz is saved in a single transaction (all rows or none).

## Testing

Only features with a Pass result below should be described as tested.

| Check | How to run | Result |
|---|---|---|
| Service tests (30 tests: validation, scoring, saving, dates, recommendations, data persistence, Simple Terms, and the AI helper using a simulated connection) | `python -m unittest discover -s tests -v` | Passed 30/30 during development. On my computer: ______ |
| Screen smoke test (opens every screen and completes a full quiz) | `python tests/ui_smoke_test.py` | Passed on my Windows computer (Python 3.14.7) |
| Live AI helper (the automated tests never contact a real AI service) | Ask one question in Simple Terms with your own key | ______ |
| Manual checklist (25 tests) | See `TEST_CHECKLIST.md` | ____ of 25 passed |

To fill the app with demo data for a presentation: `python tests/make_demo_data.py` (this writes to your real database).

## Known limitations

- Single user only, with no accounts or login. Data stays on one computer.
- Dates are typed as YYYY-MM-DD because CustomTkinter has no built-in date picker.
- Only multiple-choice questions with four choices are supported.
- The AI helper needs internet and your own API key, can be wrong, and sends what you type to the provider. On the free Google plan, that text may be used to improve Google's products.
- The Simple Terms starter list was written for Nova and has not been reviewed by a teacher. Check it against your textbook.
- The Nova app has no user accounts. The website has an account **prototype** (sign-up, login, demo 6-digit code, password reset, profile form) that stores data only in the browser and is not real security. Real accounts, Google sign-in and Apple sign-in are planned (see `website/accounts-plan.html`).
- No notifications, export, or import of questions.
- Quizzes that cover all topics are listed as "Mixed topics" in the history.
- Keyboard use is limited to the shortcuts above. Moving between buttons with the Tab key has not been tested or improved.
- Nova has not been packaged as an `.exe`. It runs with Python.
- It has been tested only by its developer, not with other students, so its benefits are unproven.

## How Nova connects to SDG 4

SDG 4 aims for inclusive, equitable, quality education and lifelong learning for everyone. Nova addresses only a small part of that goal: it gives an individual student a free tool for planning, practicing, self-checking and understanding hard terms. It does not solve access, funding or teacher shortages. UNESCO's 2023 report notes that one in four primary schools has no electricity and that technology should never replace teacher-led instruction, so the campaign website pairs the tool with an honest look at technology's limits.

## Science, technology and society

- **Science:** research on memory finds that practicing recall improves long-term retention more than rereading (Roediger and Karpicke, 2006).
- **Technology:** Nova turns that finding into quizzes with immediate feedback, a planner, and progress records.
- **Society:** students, teachers and schools decide how such tools are used. Needs such as free, offline use and data privacy shaped how Nova was designed, and easy access to answers is changing study habits, which is why Nova asks students to write and answer their own questions.

## Benefits and risks of technology in education

Benefits include wider access to resources, independent learning, immediate feedback, and better organization. Risks include overreliance on AI answers, inaccurate information, unequal access, too much screen time, and privacy concerns. The website's "Tech in Education" page covers these in detail.

## References

1. United Nations. (2026). *The Sustainable Development Goals Report 2026: Goal 4 extended report.* United Nations Statistics Division. https://unstats.un.org/sdgs/report/2026/extended-report/Extended-Report-2026_Goal-4.pdf
2. UNESCO Global Education Monitoring Report. (2023). *Global education monitoring report 2023: Technology in education: A tool on whose terms?* UNESCO. https://doi.org/10.54676/UZQV8501
3. UNESCO Austria. (n.d.). *Global Education Monitoring Report 2023: Technology in education: A tool on whose terms?* (summary page). https://www.unesco.at/en/education/education-2030/global-education-monitoring-gem-report/gem23
4. Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255. https://doi.org/10.1111/j.1467-9280.2006.01693.x
