"""Read-only git safety checks.

This module NEVER runs a git command that changes repository state
(no add/commit/push/reset/checkout/clean). It only reads state, so the
orchestrator can detect what changed and refuse to silently accept an
unexpected commit.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


class GitSafetyError(RuntimeError):
    pass


def _run(repo_root: str, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitSafetyError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


@dataclass
class GitSnapshot:
    branch: str
    head: str
    status_porcelain: str
    dirty_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "branch": self.branch,
            "head": self.head,
            "status_porcelain": self.status_porcelain,
            "dirty_files": self.dirty_files,
        }


def snapshot(repo_root: str) -> GitSnapshot:
    branch = _run(repo_root, ["branch", "--show-current"]).strip()
    head = _run(repo_root, ["rev-parse", "HEAD"]).strip()
    status = _run(repo_root, ["status", "--porcelain"])
    dirty_files = [line[3:].strip() for line in status.splitlines() if line.strip()]
    return GitSnapshot(branch=branch, head=head, status_porcelain=status, dirty_files=dirty_files)


def diff_against(repo_root: str, before: GitSnapshot) -> dict:
    """Compare current git state against a prior snapshot.

    Returns a dict describing what changed since `before`, without ever
    mutating the working tree.
    """
    after = snapshot(repo_root)

    commits_created = before.head != after.head
    branch_changed = before.branch != after.branch

    before_set = set(before.dirty_files)
    after_set = set(after.dirty_files)
    newly_dirty = sorted(after_set - before_set)
    newly_clean = sorted(before_set - after_set)  # e.g. staged/committed by the subprocess
    still_dirty_pre_existing = sorted(before_set & after_set)

    # Unified diff of tracked changes, capped so it doesn't blow up token usage
    # when handed to a review model.
    raw_diff = _run(repo_root, ["diff", "HEAD"])
    truncated = False
    if len(raw_diff) > 20000:
        raw_diff = raw_diff[:20000]
        truncated = True

    return {
        "before": before.to_dict(),
        "after": after.to_dict(),
        "commits_created": commits_created,
        "branch_changed": branch_changed,
        "newly_dirty_files": newly_dirty,
        "newly_clean_files": newly_clean,
        "pre_existing_dirty_files_untouched": still_dirty_pre_existing,
        "diff": raw_diff,
        "diff_truncated": truncated,
    }


def preflight(repo_root: str) -> GitSnapshot:
    """Run before invoking Claude. Raises if the repo isn't in a state we
    can safely reason about (e.g. not a git repo at all, or in the middle
    of a rebase/merge)."""
    try:
        merge_head = _run(repo_root, ["rev-parse", "--verify", "-q", "MERGE_HEAD"])
    except GitSafetyError:
        merge_head = ""
    if merge_head.strip():
        raise GitSafetyError(
            "Repository has an in-progress merge (MERGE_HEAD present). "
            "Resolve or abort it before running the orchestrator."
        )
    return snapshot(repo_root)
