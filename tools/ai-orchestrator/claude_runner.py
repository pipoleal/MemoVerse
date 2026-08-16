"""Invokes the official Claude Code CLI (`claude`) non-interactively.

This is the ONLY supported way this orchestrator talks to "Claude" — it does
not call the Anthropic Messages API directly. Rationale (from the Section 31
investigation): this environment already runs Claude via the Claude Code CLI
(this very orchestrator was built by that CLI), there is no ANTHROPIC_API_KEY
configured for a separate API integration, and `claude` ships an official,
documented non-interactive mode (`-p`/`--print`) built exactly for scripting.
Reusing that existing, already-authenticated infrastructure is safer than
adding a second, parallel Claude credential/integration.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

from schemas import empty_claude_report, extract_json_block

NEVER_COMMIT_INSTRUCTION = """
REGRAS OBRIGATÓRIAS PARA ESTA TAREFA:
- NÃO execute `git commit`, `git push`, nem qualquer comando de deploy.
- Implemente a mudança solicitada e deixe os arquivos alterados SEM commit, para revisão humana posterior.
- Leia primeiro docs/ai/PROJECT_CONTEXT.md, docs/ai/ARCHITECTURE.md e docs/ai/CURRENT_STATE.md para contexto do projeto antes de agir.
- Se encontrar um bloqueio real (credencial ausente, ambiguidade que impede prosseguir com segurança), pare e reporte o bloqueio em vez de tentar contornar.
""".strip()

# Env var name prefixes that belong ONLY to the GPT-review half of the
# orchestrator and must never reach the Claude subprocess. Filtering by
# prefix (rather than a fixed list of exact names) also covers any future
# OPENAI_* config var added to .env.example without needing to update this
# list — the underlying rule is "nothing in the OPENAI_ namespace is ever
# something Claude needs".
GPT_ONLY_ENV_PREFIXES = ("OPENAI_",)


def build_sanitized_claude_env() -> dict[str, str]:
    """Environment for the `claude` subprocess: a copy of this process's
    environment with every OPENAI_*-prefixed variable removed.

    This process (orchestrator.py) loads OPENAI_API_KEY into os.environ via
    _load_env() so gpt_reviewer.py can read it. subprocess.run() with no
    `env=` argument inherits the FULL parent environment by default, which
    previously meant the Claude subprocess (and anything it runs via Bash)
    could read OPENAI_API_KEY. This function is the fix: build an explicit,
    filtered copy and pass it as `env=`, so nothing in the OPENAI_ namespace
    is ever visible to Claude. Everything else (PATH, HOME/USERPROFILE,
    APPDATA, ANTHROPIC_*, node/npm paths, etc.) is preserved unchanged so
    the `claude` CLI keeps working normally.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(GPT_ONLY_ENV_PREFIXES)
    }


# Technical (not just textual) blocks on dangerous Bash invocations, passed
# to `claude --disallowedTools`. These are enforced by the Claude Code
# permission system itself — verified empirically (see
# tools/ai-orchestrator/security_tests.py) that a matched command is denied
# BEFORE execution, even when the task prompt explicitly asks for it, and
# even when chained with other commands via `&&`. This is defense-in-depth
# on top of NEVER_COMMIT_INSTRUCTION, not a replacement for it — pattern
# matching on the Bash command string cannot cover every possible way to
# invoke a given program (e.g. an unlisted alias or interpreter path). The
# prompt instruction and the post-hoc HEAD-comparison checks in
# git_safety.py remain in place as additional layers.
DISALLOWED_TOOL_PATTERNS = [
    # Irreversible / history-rewriting git operations.
    "Bash(git commit*)",
    "Bash(git push*)",
    "Bash(git reset*)",
    "Bash(git clean*)",
    "Bash(git checkout*)",
    "Bash(git rm*)",
    "Bash(git merge*)",
    "Bash(git rebase*)",
    # Database migrations (any common way manage.py might be invoked).
    "Bash(python manage.py migrate*)",
    "Bash(python3 manage.py migrate*)",
    "Bash(./manage.py migrate*)",
    "Bash(manage.py migrate*)",
    "Bash(py manage.py migrate*)",
    # Common deploy entry points that might exist in this or similar repos.
    "Bash(docker compose up*)",
    "Bash(docker-compose up*)",
    "Bash(vercel *)",
    "Bash(npm run deploy*)",
]


@dataclass
class ClaudeRunResult:
    ok: bool
    raw_stdout: str
    raw_stderr: str
    final_text: str
    report: dict
    session_id: str | None
    total_cost_usd: float | None
    error: str | None = None


def build_task_prompt(task_description: str, report_schema_description: str) -> str:
    return (
        f"{NEVER_COMMIT_INSTRUCTION}\n\n"
        f"TAREFA:\n{task_description}\n\n"
        f"AO TERMINAR:\n{report_schema_description}"
    )


def run_claude_task(
    *,
    repo_root: str,
    prompt: str,
    permission_mode: str = "acceptEdits",
    model: str | None = None,
    timeout_seconds: int = 1800,
) -> ClaudeRunResult:
    # shutil.which() applies PATHEXT resolution (finds claude.cmd/.ps1 on
    # Windows) — a bare "claude" string often fails under subprocess.run
    # without shell=True even though the same name resolves fine in a shell.
    claude_executable = shutil.which("claude")
    if claude_executable is None:
        return ClaudeRunResult(
            ok=False,
            raw_stdout="",
            raw_stderr="",
            final_text="",
            report=empty_claude_report(
                "Comando 'claude' não encontrado no PATH. A CLI do Claude Code precisa "
                "estar instalada e acessível para este orquestrador funcionar."
            ),
            session_id=None,
            total_cost_usd=None,
            error="claude_cli_not_found",
        )

    # The prompt is piped via stdin (positional `prompt` arg omitted) rather
    # than passed as a CLI argument. On Windows, `claude` resolves to a
    # .cmd/.ps1 shim, which subprocess.run() can only invoke through
    # cmd.exe's own command-line parsing — a long or multi-line argument
    # gets silently truncated at the first newline there (confirmed: Claude
    # received only the first line of the prompt when passed as argv).
    # Piping via stdin sidesteps that entirely and works identically on
    # Windows/macOS/Linux.
    args = [
        claude_executable,
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        permission_mode,
    ]
    if model:
        args.extend(["--model", model])
    # --disallowedTools is variadic (consumes every following token that
    # doesn't itself start with "--"). Keep it as the LAST thing appended so
    # nothing after it (e.g. --model) risks being swallowed as an extra
    # pattern instead of its own flag.
    args.extend(["--disallowedTools", *DISALLOWED_TOOL_PATTERNS])

    try:
        proc = subprocess.run(
            args,
            cwd=repo_root,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=build_sanitized_claude_env(),
        )
    except subprocess.TimeoutExpired as exc:
        return ClaudeRunResult(
            ok=False,
            raw_stdout=exc.stdout or "",
            raw_stderr=exc.stderr or "",
            final_text="",
            report=empty_claude_report(f"Timeout após {timeout_seconds}s executando o Claude CLI."),
            session_id=None,
            total_cost_usd=None,
            error="timeout",
        )
    except FileNotFoundError:
        return ClaudeRunResult(
            ok=False,
            raw_stdout="",
            raw_stderr="",
            final_text="",
            report=empty_claude_report(
                "Comando 'claude' não encontrado no PATH. A CLI do Claude Code precisa "
                "estar instalada e acessível para este orquestrador funcionar."
            ),
            session_id=None,
            total_cost_usd=None,
            error="claude_cli_not_found",
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    parsed: dict | None = None
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None

    if parsed is not None and isinstance(parsed, dict):
        final_text = parsed.get("result", "") or ""
        session_id = parsed.get("session_id")
        total_cost_usd = parsed.get("total_cost_usd")
        is_error = bool(parsed.get("is_error", proc.returncode != 0))
    else:
        # Fall back to treating raw stdout as the final text if JSON parsing
        # failed (e.g. CLI printed something unexpected).
        final_text = stdout
        session_id = None
        total_cost_usd = None
        is_error = proc.returncode != 0

    report = extract_json_block(final_text)
    if report is None:
        report = empty_claude_report(
            "O Claude não terminou a resposta com o bloco JSON estruturado esperado. "
            "Trate este resultado com cautela e revise manualmente."
        )

    return ClaudeRunResult(
        ok=proc.returncode == 0 and not is_error,
        raw_stdout=stdout,
        raw_stderr=stderr,
        final_text=final_text,
        report=report,
        session_id=session_id,
        total_cost_usd=total_cost_usd,
        error=None if proc.returncode == 0 else f"exit_code={proc.returncode}",
    )
