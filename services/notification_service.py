"""Builds the text of a task reminder from the planner's saved tasks."""
from datetime import date, timedelta

from services import planner_service


def build_reminder(days, include_overdue=True, today=None):
    """A short reminder about overdue tasks and tasks due within `days` days, or None if there is nothing."""
    today = today or date.today()
    groups = planner_service.group_tasks(planner_service.list_tasks(), today)
    limit = today + timedelta(days=days)
    soon = [t for t in groups["upcoming"] if date.fromisoformat(t["due_date"]) <= limit]
    overdue = groups["overdue"] if include_overdue else []
    if not soon and not overdue:
        return None
    lines = []
    if overdue:
        lines.append(f"{len(overdue)} overdue task{'' if len(overdue) == 1 else 's'}.")
    if soon:
        lines.append(f"{len(soon)} task{'' if len(soon) == 1 else 's'} due within {days} day{'' if days == 1 else 's'}.")
    urgent = (overdue + soon)[0]  # overdue tasks come first, and each group is sorted by due date
    lines.append(f"Next: {urgent['title']} - {planner_service.due_label(urgent['due_date'], today)}")
    return "\n".join(lines)
