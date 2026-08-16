#!/usr/bin/env python3
"""MemoVerse AI Orchestrator — Claude (implementa) x GPT (revisa) x Humano (decide).

Uso:
    python orchestrator.py selftest
    python orchestrator.py run "<descrição da tarefa>"
    python orchestrator.py resume <task_id>
    python orchestrator.py list

Regras invioláveis deste script (não altere sem entender por quê — ver README.md):
  - NUNCA roda `git add`, `git commit`, `git push`, `git reset`, `git checkout .`
    ou qualquer comando destrutivo/de publicação. git_safety.py é somente leitura.
  - NUNCA decide sozinho se uma implementação está pronta — a aprovação final
    é sempre um humano digitando uma opção no menu.
  - Instrui explicitamente o Claude, em todo prompt de tarefa, a não commitar/
    dar push/fazer deploy (ver claude_runner.NEVER_COMMIT_INSTRUCTION).
"""
from __future__ import annotations

import argparse
import os
import sys

# On Windows the console codepage (e.g. cp1252) can't encode characters
# Claude commonly outputs (emoji, accented text). Without this, a report
# summary containing e.g. an emoji crashes the whole run mid-print.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import claude_runner
import git_safety
import gpt_reviewer
import secrets_scanner
import state_store
from schemas import CLAUDE_REPORT_SCHEMA_DESCRIPTION

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TOOL_DIR))
DOCS_AI_DIR = os.path.join(REPO_ROOT, "docs", "ai")

SELFTEST_TASK = (
    "Leia o arquivo README.md na raiz do repositório e descreva, em no máximo "
    "duas frases, do que ele fala. NÃO modifique, crie ou apague nenhum arquivo — "
    "esta é uma tarefa somente leitura para testar o orquestrador."
)


def _load_env() -> None:
    env_path = os.path.join(TOOL_DIR, ".env")
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        # Minimal manual fallback so a missing `python-dotenv` doesn't hard-fail.
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def _config() -> dict:
    return {
        "openai_api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
        "openai_model": os.environ.get("OPENAI_MODEL", gpt_reviewer.DEFAULT_GPT_MODEL).strip(),
        "claude_permission_mode": os.environ.get("CLAUDE_PERMISSION_MODE", "acceptEdits").strip(),
        "claude_model": os.environ.get("CLAUDE_MODEL", "").strip() or None,
        "max_gpt_reviews": int(os.environ.get("MAX_GPT_REVIEWS", "3")),
        "max_correction_attempts": int(os.environ.get("MAX_CORRECTION_ATTEMPTS", "3")),
        "claude_timeout_seconds": int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "1800")),
    }


def _load_project_context() -> str:
    parts = []
    if os.path.isdir(DOCS_AI_DIR):
        for name in sorted(os.listdir(DOCS_AI_DIR)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(DOCS_AI_DIR, name), "r", encoding="utf-8") as f:
                parts.append(f"### {name}\n\n{f.read()}")
    return "\n\n".join(parts)


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _print_claude_report(report: dict) -> None:
    _print_header("RELATÓRIO DO CLAUDE (implementação)")
    print(f"status: {report.get('status')}")
    print(f"summary: {report.get('summary')}")
    print(f"files_changed: {report.get('files_changed')}")
    print(f"tests_run: {report.get('tests_run')}")
    print(f"blockers: {report.get('blockers')}")
    print(f"notes_for_reviewer: {report.get('notes_for_reviewer')}")


def _print_gpt_review(review: dict | None) -> None:
    _print_header("REVISÃO DO GPT")
    if review is None:
        print("(revisão do GPT não disponível — ver notas acima)")
        return
    print(f"verdict: {review.get('verdict')}")
    print(f"summary: {review.get('summary')}")
    for issue in review.get("issues") or []:
        print(f"  - [{issue.get('severity')}] {issue.get('description')} ({issue.get('file')})")
    if review.get("suggested_correction_prompt"):
        print(f"suggested_correction_prompt: {review.get('suggested_correction_prompt')}")


def _print_git_diff_info(info: dict) -> None:
    _print_header("MUDANÇAS NO GIT (somente leitura, nada foi commitado por este script)")
    print(f"commits_created_by_claude: {info.get('commits_created')}  "
          f"{'!!! VIOLAÇÃO DE REGRA - CLAUDE COMMITOU !!!' if info.get('commits_created') else ''}")
    print(f"branch_changed: {info.get('branch_changed')}")
    print(f"newly_dirty_files: {info.get('newly_dirty_files')}")
    print(f"pre_existing_dirty_files_untouched: {info.get('pre_existing_dirty_files_untouched')}")
    if info.get("diff_truncated"):
        print("(diff truncado por tamanho ao ser salvo/enviado para revisão)")


def _human_approval_menu() -> str:
    _print_header("DECISÃO HUMANA")
    print("[1] APROVAR")
    print("[2] PEDIR CORREÇÃO")
    print("[3] REVISAR NOVAMENTE (rodar o GPT de novo sobre o mesmo resultado)")
    print("[4] REJEITAR")
    print("[5] PARAR (salva o estado e sai; pode retomar depois com `resume <task_id>`)")
    while True:
        choice = input("Escolha [1-5]: ").strip()
        if choice in {"1", "2", "3", "4", "5"}:
            return choice
        print("Opção inválida.")


def _run_claude_phase(state: state_store.TaskState, cfg: dict, prompt: str) -> None:
    state.transition("TASK_RUNNING", note="Invocando Claude CLI")
    state_store.save(state)

    baseline = git_safety.GitSnapshot(**state.git_baseline)
    result = claude_runner.run_claude_task(
        repo_root=REPO_ROOT,
        prompt=prompt,
        permission_mode=cfg["claude_permission_mode"],
        model=cfg["claude_model"],
        timeout_seconds=cfg["claude_timeout_seconds"],
    )

    diff_info = git_safety.diff_against(REPO_ROOT, baseline)
    state.last_claude_report = result.report
    state.last_git_diff_info = diff_info
    state.transition(
        "IMPLEMENTATION_READY",
        note=f"Claude ok={result.ok} error={result.error}",
    )
    state_store.save(state)

    _print_claude_report(result.report)
    _print_git_diff_info(diff_info)
    if not result.ok:
        print(f"\n[aviso] A execução do Claude CLI reportou um erro: {result.error}")
        if result.raw_stderr:
            print(f"stderr (parcial): {result.raw_stderr[:2000]}")


def _run_gpt_phase(state: state_store.TaskState, cfg: dict, project_context: str) -> None:
    state.transition("GPT_REVIEW", note="Enviando para revisão do GPT")
    state_store.save(state)

    if not cfg["openai_api_key"]:
        print("\n[info] OPENAI_API_KEY não configurada — pulando revisão automática do GPT. "
              "Configure tools/ai-orchestrator/.env para habilitar essa etapa.")
        state.last_gpt_review = None
        state_store.save(state)
        return

    if state.gpt_review_count >= state.max_gpt_reviews:
        print(f"\n[aviso] Limite de revisões do GPT atingido ({state.max_gpt_reviews}). "
              "Pulando nova chamada ao GPT.")
        return

    diff_text = (state.last_git_diff_info or {}).get("diff", "")
    is_safe, findings = secrets_scanner.diff_is_safe_to_send(diff_text)
    state.last_secrets_scan = {
        "safe": is_safe,
        "findings": [f.to_dict() for f in findings],
    }
    state_store.save(state)
    if not is_safe:
        _print_header("🔴 SCANNER DE SEGREDOS: ENVIO AO GPT BLOQUEADO")
        print("Padrões de credencial foram encontrados em linhas adicionadas do diff. "
              "O diff NÃO foi enviado para a API da OpenAI. Revise manualmente antes de continuar:")
        for f in findings:
            print(f"  - [{f.pattern_name}] linha {f.line_number}: {f.redacted_snippet}")
        state.last_gpt_review = None
        state_store.save(state)
        return

    result = gpt_reviewer.review_with_gpt(
        api_key=cfg["openai_api_key"],
        task_description=state.task_description,
        claude_report=state.last_claude_report or {},
        git_diff_info=state.last_git_diff_info or {},
        project_context=project_context,
        model=cfg["openai_model"],
    )
    state.gpt_review_count += 1
    state.last_gpt_review = result.review
    state_store.save(state)

    _print_gpt_review(result.review)
    if not result.ok:
        print(f"\n[aviso] Chamada ao GPT falhou: {result.error}")


def _task_loop(state: state_store.TaskState, cfg: dict, project_context: str, initial_prompt: str) -> None:
    prompt = initial_prompt
    while True:
        _run_claude_phase(state, cfg, prompt)
        _run_gpt_phase(state, cfg, project_context)

        state.transition("WAITING_HUMAN_APPROVAL")
        state_store.save(state)
        choice = _human_approval_menu()

        if choice == "1":  # APROVAR
            state.transition("COMPLETED", note="Aprovado pelo humano")
            state_store.save(state)
            print(f"\nTarefa {state.task_id} concluída (COMPLETED). "
                  "Nada foi commitado/pushado automaticamente — faça isso manualmente quando quiser.")
            return

        if choice == "2":  # PEDIR CORREÇÃO
            if state.correction_attempts >= state.max_correction_attempts:
                state.transition(
                    "BLOCKED",
                    note=f"Limite de tentativas de correção atingido ({state.max_correction_attempts})",
                )
                state_store.save(state)
                print(f"\n[BLOCKED] Limite de {state.max_correction_attempts} correções atingido. "
                      "Intervenção humana direta é necessária.")
                return
            correction = None
            if state.last_gpt_review:
                correction = state.last_gpt_review.get("suggested_correction_prompt")
            if not correction:
                correction = input(
                    "Digite a instrução de correção para o Claude: "
                ).strip()
            state.correction_attempts += 1
            state.transition("CORRECTION_REQUIRED", note=correction[:200])
            state_store.save(state)
            # Re-baseline git before the next Claude invocation so the next
            # diff reflects only what THIS correction round changes.
            state.git_baseline = git_safety.snapshot(REPO_ROOT).to_dict()
            state_store.save(state)
            prompt = claude_runner.build_task_prompt(
                f"Correção solicitada sobre o trabalho anterior:\n{correction}",
                CLAUDE_REPORT_SCHEMA_DESCRIPTION,
            )
            continue

        if choice == "3":  # REVISAR NOVAMENTE
            if state.gpt_review_count >= state.max_gpt_reviews:
                print(f"\n[aviso] Limite de {state.max_gpt_reviews} revisões do GPT já atingido.")
                continue
            _run_gpt_phase(state, cfg, project_context)
            continue

        if choice == "4":  # REJEITAR
            state.transition("BLOCKED", note="Rejeitado pelo humano")
            state_store.save(state)
            print(f"\nTarefa {state.task_id} marcada como BLOCKED (rejeitada). "
                  "As mudanças NÃO foram revertidas automaticamente — revise/descarte manualmente se quiser.")
            return

        if choice == "5":  # PARAR
            state_store.save(state)
            print(f"\nEstado salvo. Retome com: python orchestrator.py resume {state.task_id}")
            return


def cmd_run(task_description: str) -> None:
    cfg = _config()
    project_context = _load_project_context()

    try:
        baseline = git_safety.preflight(REPO_ROOT)
    except git_safety.GitSafetyError as exc:
        print(f"[BLOCKED] Pré-checagem de segurança do git falhou: {exc}")
        sys.exit(1)

    task_id = state_store.new_task_id(task_description)
    state = state_store.TaskState(
        task_id=task_id,
        task_description=task_description,
        max_correction_attempts=cfg["max_correction_attempts"],
        max_gpt_reviews=cfg["max_gpt_reviews"],
        git_baseline=baseline.to_dict(),
    )
    state_store.save(state)

    print(f"Task ID: {task_id}")
    print(f"Git baseline: branch={baseline.branch} head={baseline.head}")
    if baseline.dirty_files:
        print(f"[info] Havia {len(baseline.dirty_files)} arquivo(s) já modificado(s)/não rastreado(s) "
              "antes desta tarefa — eles serão preservados como estavam na comparação de diff.")

    prompt = claude_runner.build_task_prompt(task_description, CLAUDE_REPORT_SCHEMA_DESCRIPTION)
    _task_loop(state, cfg, project_context, prompt)


def cmd_resume(task_id: str) -> None:
    cfg = _config()
    project_context = _load_project_context()
    state = state_store.load(task_id)
    print(f"Retomando task {task_id} (estado salvo: {state.state})")

    if state.state == "CORRECTION_REQUIRED":
        correction_note = state.history[-1]["note"] if state.history else ""
        prompt = claude_runner.build_task_prompt(
            f"Correção solicitada sobre o trabalho anterior:\n{correction_note}",
            CLAUDE_REPORT_SCHEMA_DESCRIPTION,
        )
    else:
        prompt = claude_runner.build_task_prompt(state.task_description, CLAUDE_REPORT_SCHEMA_DESCRIPTION)

    _task_loop(state, cfg, project_context, prompt)


def cmd_list() -> None:
    ids = state_store.list_task_ids()
    if not ids:
        print("Nenhuma tarefa salva ainda.")
        return
    for task_id in ids:
        state = state_store.load(task_id)
        print(f"{task_id}  [{state.state}]  {state.task_description[:60]}")


def cmd_selftest() -> None:
    print("Rodando autoteste (tarefa fictícia, somente leitura, sem tocar no MemoVerse de verdade)...")
    cmd_run(SELFTEST_TASK)


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Inicia uma nova tarefa")
    p_run.add_argument("task_description")

    p_resume = sub.add_parser("resume", help="Retoma uma tarefa salva")
    p_resume.add_argument("task_id")

    sub.add_parser("list", help="Lista tarefas salvas")
    sub.add_parser("selftest", help="Roda a tarefa de autoteste obrigatória antes do primeiro uso real")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args.task_description)
    elif args.command == "resume":
        cmd_resume(args.task_id)
    elif args.command == "list":
        cmd_list()
    elif args.command == "selftest":
        cmd_selftest()


if __name__ == "__main__":
    main()
