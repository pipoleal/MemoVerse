"""Local, deterministic secret scanner for diffs before they leave the machine.

Runs against the `git diff HEAD` text right before it would be sent to the
OpenAI API for GPT review. Purely regex-based, no network calls, no external
services, no dependencies beyond the standard library — intentionally simple
and easy to audit, per the request that motivated this file: catch an
accidentally hardcoded credential in a TRACKED file (the .env file itself is
already excluded from `git diff` by .gitignore — see git_safety.py and
README.md — this scanner is the second layer, for secrets that end up
somewhere else by mistake).

This is a best-effort net, not a guarantee: it only catches patterns listed
below. A cleverly obfuscated or unusually-shaped secret can still slip
through. That's an accepted, documented trade-off for staying simple,
dependency-free, and auditable in a few minutes of reading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Each entry: (human-readable name, compiled pattern). Patterns are
# intentionally conservative (favor missing an unusual secret shape over
# constantly false-positiving on normal code) but cover the credential
# formats most likely to show up by accident in this project and in general.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI API key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}")),
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS-style secret assignment", re.compile(
        r"aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{30,}['\"]", re.IGNORECASE
    )),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{30,}")),
    ("Mercado Pago access token", re.compile(r"APP_USR-[A-Za-z0-9\-]{10,}")),
    ("Mercado Pago test token", re.compile(r"TEST-[A-Za-z0-9\-]{10,}")),
    ("Private key block", re.compile(
        r"-----BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----"
    )),
    ("JWT-shaped token", re.compile(
        r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    )),
    ("Generic secret-like assignment", re.compile(
        r"(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|"
        r"auth[_-]?token|private[_-]?key|password|passwd)\s*[:=]\s*"
        r"['\"][A-Za-z0-9_\-/+=]{12,}['\"]",
        re.IGNORECASE,
    )),
]


@dataclass
class SecretFinding:
    pattern_name: str
    line_number: int | None
    redacted_snippet: str

    def to_dict(self) -> dict:
        return {
            "pattern_name": self.pattern_name,
            "line_number": self.line_number,
            "redacted_snippet": self.redacted_snippet,
        }


def _redact(matched_text: str) -> str:
    if len(matched_text) <= 8:
        return "*" * len(matched_text)
    return matched_text[:4] + "…REDACTED…" + matched_text[-4:]


def scan_text(text: str) -> list[SecretFinding]:
    """Scan arbitrary text (typically a `git diff HEAD` body) for secret-like
    patterns. Only lines added by the diff (starting with '+', not '+++')
    are considered — removed lines and unchanged context lines are not new
    exposure, and skipping them cuts noise substantially.
    """
    findings: list[SecretFinding] = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for name, pattern in _PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    SecretFinding(
                        pattern_name=name,
                        line_number=line_number,
                        redacted_snippet=_redact(match.group(0)),
                    )
                )
    return findings


def diff_is_safe_to_send(diff_text: str) -> tuple[bool, list[SecretFinding]]:
    """Returns (is_safe, findings). is_safe is False if any secret-like
    pattern was found in an added line — callers must not send diff_text
    anywhere external (e.g. to the GPT review API) when is_safe is False.
    """
    findings = scan_text(diff_text or "")
    return (len(findings) == 0, findings)
