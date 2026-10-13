"""Gathers the numbers shown on the Dashboard. Everything comes from saved data, nothing is hard-coded."""
from services import planner_service, progress_service
from services.study_service import _fetch_all

UPCOMING_LIMIT = 5
RECENT_LIMIT = 5


def get_dashboard_data():
    counts = _fetch_all(
        """SELECT (SELECT COUNT(*) FROM subjects) AS subjects,
                  (SELECT COUNT(*) FROM topics) AS topics,
                  (SELECT COUNT(*) FROM topics WHERE status = 'completed') AS topics_done""")[0]
    tasks = planner_service.list_tasks()
    groups = planner_service.group_tasks(tasks)
    pending = sorted(groups["overdue"] + groups["upcoming"], key=lambda task: task["due_date"])
    threshold = progress_service.get_review_threshold()
    return {
        "counts": counts,
        "task_summary": planner_service.summarize(tasks),
        "total_tasks": len(tasks),
        "upcoming": pending[:UPCOMING_LIMIT],
        "recent_quizzes": progress_service.quiz_history()[:RECENT_LIMIT],
        "threshold": threshold,
        "review_count": len(progress_service.topic_recommendations(threshold)["items"]),
    }