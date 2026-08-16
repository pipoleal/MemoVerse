"""Persists orchestrator task state as JSON files under state/.

The state directory is local/ephemeral and gitignored — it is not a shared
memory mechanism (that's docs/ai/). It exists so a task can be resumed or
audited after the process exits.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

STATE_DIR = os.path.join(os.path.dirname(__file__), "state")

# Finite state machine states, per spec.
STATES = (
    "IDLE",
    "TASK_RUNNING",
    "IMPLEMENTATION_READY",
    "GPT_REVIEW",
    "WAITING_HUMAN_APPROVAL",
    "CORRECTION_REQUIRED",
    "BLOCKED",
    "COMPLETED",
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:40] or "task"


@dataclass
class TaskState:
    task_id: str
    task_description: str
    state: str = "IDLE"
    correction_attempts: int = 0
    gpt_review_count: int = 0
    max_correction_attempts: int = 3
    max_gpt_reviews: int = 3
    git_baseline: dict = field(default_factory=dict)
    history: list = field(default_factory=list)  # list of {state, timestamp, note}
    last_claude_report: dict | None = None
    last_gpt_review: dict | None = None
    last_git_diff_info: dict | None = None
    last_secrets_scan: dict | None = None  # {"safe": bool, "findings": [...]} — redacted, never raw secret values

    def transition(self, new_state: str, note: str = "") -> None:
        if new_state not in STATES:
            raise ValueError(f"Unknown state: {new_state}")
        self.state = new_state
        self.history.append({"state": new_state, "timestamp": time.time(), "note": note})

    def to_dict(self) -> dict:
        return asdict(self)


def new_task_id(task_description: str) -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{_slugify(task_description)}"


def path_for(task_id: str) -> str:
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, f"{task_id}.json")


def save(state: TaskState) -> None:
    with open(path_for(state.task_id), "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)


def load(task_id: str) -> TaskState:
    with open(path_for(task_id), "r", encoding="utf-8") as f:
        data = json.load(f)
    return TaskState(**data)


def list_task_ids() -> list[str]:
    if not os.path.isdir(STATE_DIR):
        return []
    return sorted(
        fname[:-5] for fname in os.listdir(STATE_DIR) if fname.endswith(".json")
    )
