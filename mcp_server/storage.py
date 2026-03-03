"""
💾 Storage Module — Task Persistence
======================================
Handles reading/writing tasks to a JSON file.

WHY JSON FILE?
We're keeping it simple and human-readable. You can open
tasks.json in any editor and see exactly what's stored.
No database setup needed — just a file.

TASK SCHEMA:
{
  "id": "uuid-string",
  "title": "Buy groceries",
  "priority": "high" | "medium" | "low",
  "status": "pending" | "done",
  "created_at": "2026-03-02T23:30:00",
  "due_date": "2026-03-03" | null
}
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Where tasks are saved on disk
TASKS_FILE = Path(__file__).parent / "tasks.json"


def _load() -> list[dict]:
    """Load all tasks from the JSON file."""
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE, "r") as f:
        return json.load(f)


def _save(tasks: list[dict]) -> None:
    """Save all tasks to the JSON file."""
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def add_task(title: str, priority: str = "medium", due_date: str | None = None) -> dict:
    """
    Add a new task and return it.

    Args:
        title: Task description
        priority: "high", "medium", or "low"
        due_date: Optional date string like "2026-03-05"
    """
    tasks = _load()
    task = {
        "id": str(uuid.uuid4())[:8],   # Short 8-char ID for readability
        "title": title,
        "priority": priority.lower(),
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "due_date": due_date,
    }
    tasks.append(task)
    _save(tasks)
    return task


def list_tasks(status: str | None = None, priority: str | None = None) -> list[dict]:
    """
    Return tasks, optionally filtered by status and/or priority.

    Args:
        status: Filter by "pending" or "done" (None = all)
        priority: Filter by "high", "medium", or "low" (None = all)
    """
    tasks = _load()
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if priority:
        tasks = [t for t in tasks if t["priority"] == priority]
    return tasks


def complete_task(task_id: str) -> dict | None:
    """
    Mark a task as done by its ID.
    Returns the updated task, or None if not found.
    """
    tasks = _load()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "done"
            task["completed_at"] = datetime.now().isoformat(timespec="seconds")
            _save(tasks)
            return task
    return None


def delete_task(task_id: str) -> bool:
    """
    Delete a task by its ID.
    Returns True if deleted, False if not found.
    """
    tasks = _load()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    if len(new_tasks) == len(tasks):
        return False  # Nothing was removed
    _save(new_tasks)
    return True


def get_summary() -> dict:
    """Return a summary of all tasks."""
    tasks = _load()
    today = datetime.now().date().isoformat()

    pending = [t for t in tasks if t["status"] == "pending"]
    done = [t for t in tasks if t["status"] == "done"]
    overdue = [
        t for t in pending
        if t.get("due_date") and t["due_date"] < today
    ]
    high_priority = [t for t in pending if t["priority"] == "high"]

    return {
        "total": len(tasks),
        "pending": len(pending),
        "done": len(done),
        "overdue": len(overdue),
        "high_priority_pending": len(high_priority),
    }
