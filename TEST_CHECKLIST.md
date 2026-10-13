# Nova test checklist

Fill in **Result** with Pass or Fail while you test, and describe any problem in **Notes**.
Only claim a feature is tested when its row says Pass.

Automated checks (run from the `Nova` folder):

- `python -m unittest discover -s tests -v`  Result: ______
- `python tests/ui_smoke_test.py`            Result: ______

| # | Area | Steps | Expected | Result | Notes |
|---|------|-------|----------|--------|-------|
| 1 | Navigation | Click every sidebar item, then press Ctrl+1 to Ctrl+5 | Each screen opens, and the active item is highlighted | | |
| 2 | Resizing | Drag the window to its smallest size, then maximize | Nothing important is cut off or hidden | | |
| 3 | Empty states | Start with no data and open every screen | Each screen explains what to do next | | |
| 4 | Subjects | Add, edit and delete a subject | Changes appear, and deleting asks first and lists what else is removed | | |
| 5 | Subject input | Try an empty name, a duplicate, and the same name in different capitals | A red message appears, and nothing is saved | | |
| 6 | Topics | Add, edit and delete topics | Changes appear, and deleting asks first | | |
| 7 | Topic status | Change a topic to Reviewed, then Completed | The color changes and the completed count updates | | |
| 8 | Planner add | Add a task with a due date | It appears under Upcoming | | |
| 9 | Planner input | Try an empty title and the dates 12/10/2026 and 2026-13-40 | A red message appears each time | | |
| 10 | Overdue | Add a task due yesterday | It appears under Overdue in red, with "Overdue by 1 day" | | |
| 11 | Complete task | Tick a task's checkbox, then untick it | It moves to Completed with a strikethrough, and back | | |
| 12 | Edit and delete task | Edit a task, then delete one | Changes appear, and deleting asks first | | |
| 13 | Sample quiz | Click Load sample questions | A Sample subject appears with 6 questions tagged Sample content | | |
| 14 | Own question | Add a question with 4 choices | It appears in the list | | |
| 15 | Question input | Try an empty question, an empty choice, and duplicate choices | A red message appears each time | | |
| 16 | Taking a quiz | Start a quiz | Next stays disabled until you choose, and no correct answer is shown | | |
| 17 | Scoring | Answer 1 question wrongly on purpose and finish | The score and the correct/incorrect counts match what you chose | | |
| 18 | Review | Check the results review | Wrong answers show your answer and the correct answer | | |
| 19 | Saved results | Finish a quiz, then open My Progress | The attempt appears in the history | | |
| 20 | Recommendations | Fail one topic on purpose, in 3 or more quizzes | The topic is listed with a reason and numbers | | |
| 21 | Not enough data | Check My Progress with fewer than 3 quizzes | The average says Not enough data | | |
| 22 | Threshold | Change the Review threshold | The suggestions update, and the choice is kept after restart | | |
| 23 | Dashboard | Compare the Dashboard numbers with the other screens | Subjects, topics, tasks, deadlines and quizzes all match | | |
| 24 | Persistence | Close the app, then reopen it | All data is still there | | |
| 25 | Database error | Close the app. Copy `%APPDATA%\Nova\nova.db` somewhere safe. Replace the original with a text file named `nova.db`. Start the app | A message says Nova could not open its database, and no crash trace appears. Afterwards, restore your copy | | |

Known limitations to mention: single user, dates typed as YYYY-MM-DD, multiple-choice only, data stored on this computer only, benefits not tested with students.

## Version 1.5 additions (do these by hand once)

- [ ] Run `py main.py`. The Nova window opens, and closing it ends the program (check Task Manager).
- [ ] Press the three-line button: the menu hides and shows, and the content widens. Press Ctrl+B, same result. Restart: the choice is remembered.
- [ ] Shrink the window under 900 px wide: the menu becomes a drawer you can close by clicking outside it.
- [ ] Scroll every screen with the mouse wheel and touchpad: only the content moves, never the whole window.
- [ ] Settings > AI connection: paste a key. The green dot appears at the top right.
- [ ] Nova AI: ask a question. The answer streams in. Press Stop mid-answer: it stops and keeps what was written.
- [ ] Attach a photo, a PDF and a Word file (button, drag and drop, and paste). Click Summarize. The answer mentions the file's real content.
- [ ] Click Make a quiz. Answer one wrongly: the explanation appears. Click Save to my subjects, then find it in Practice Quizzes.
- [ ] Attach a .exe or a file over 12 MB: Nova refuses with a clear message.
- [ ] History: reopen an earlier chat and its quiz card.
- [ ] Switch Light, Dark, System and Custom in Settings. Turn on Reduce transparency: panels become solid.
