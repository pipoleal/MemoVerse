"""Sends Claude's implementation report + diff to GPT (OpenAI API) for review.

Uses the official `openai` Python SDK. Requires OPENAI_API_KEY to be set in
the environment (loaded from tools/ai-orchestrator/.env by orchestrator.py).
This module never touches the filesystem or git — it only reads the
already-collected report/diff data it's given and returns GPT's structured
verdict.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from schemas import GPT_REVIEW_SCHEMA_DESCRIPTION, empty_gpt_review, extract_json_block

DEFAULT_GPT_MODEL = "gpt-4o"

SYSTEM_PROMPT = """
Você é o revisor técnico de um pipeline de desenvolvimento automatizado do projeto MemoVerse.
Outra IA (Claude) acabou de implementar uma tarefa de código. Sua função é revisar o que foi
feito com ceticismo profissional: aponte bugs reais, riscos de segurança, e desvios do que foi
pedido. Não reescreva o código você mesmo — apenas avalie e, se necessário, sugira uma instrução
de correção clara para o Claude executar.

Você NÃO tem acesso ao sistema de arquivos real — baseie-se apenas no diff e no relatório fornecidos.
Se o diff foi truncado ou a informação for insuficiente para um julgamento seguro, diga isso
explicitamente em vez de inventar uma avaliação.
""".strip()


@dataclass
class GptReviewResult:
    ok: bool
    review: dict
    raw_response: str
    error: str | None = None


def _build_user_message(*, task_description: str, claude_report: dict, git_diff_info: dict, project_context: str) -> str:
    parts = [
        "## Contexto do projeto (docs/ai/)",
        project_context[:12000],
        "",
        "## Tarefa original dada ao Claude",
        task_description,
        "",
        "## Relatório estruturado do Claude",
        json.dumps(claude_report, ensure_ascii=False, indent=2),
        "",
        "## Estado do git antes/depois",
        f"Commits criados pelo Claude durante a execução: {git_diff_info.get('commits_created')}",
        f"Branch alterada: {git_diff_info.get('branch_changed')}",
        f"Arquivos novos/modificados: {git_diff_info.get('newly_dirty_files')}",
        f"Arquivos pré-existentes sujos e não tocados: {git_diff_info.get('pre_existing_dirty_files_untouched')}",
        "",
        "## Diff (git diff HEAD, pode estar truncado)",
        "```diff",
        git_diff_info.get("diff", "")[:20000],
        "```",
    ]
    if git_diff_info.get("diff_truncated"):
        parts.append("\n(diff truncado por tamanho — pode haver mais mudanças além das mostradas)")
    parts.append("\n" + GPT_REVIEW_SCHEMA_DESCRIPTION)
    return "\n".join(parts)


def review_with_gpt(
    *,
    api_key: str,
    task_description: str,
    claude_report: dict,
    git_diff_info: dict,
    project_context: str,
    model: str = DEFAULT_GPT_MODEL,
) -> GptReviewResult:
    try:
        from openai import OpenAI
    except ImportError:
        return GptReviewResult(
            ok=False,
            review=empty_gpt_review(
                "Pacote 'openai' não está instalado. Rode: pip install -r requirements.txt"
            ),
            raw_response="",
            error="openai_not_installed",
        )

    client = OpenAI(api_key=api_key)
    user_message = _build_user_message(
        task_description=task_description,
        claude_report=claude_report,
        git_diff_info=git_diff_info,
        project_context=project_context,
    )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the human as a blocker, not silently swallowed
        return GptReviewResult(
            ok=False,
            review=empty_gpt_review(f"Erro ao chamar a API da OpenAI: {exc}"),
            raw_response="",
            error=str(exc),
        )

    raw_text = completion.choices[0].message.content or ""
    review = extract_json_block(raw_text)
    if review is None:
        review = empty_gpt_review(
            "GPT não retornou um JSON válido no formato esperado. Revise manualmente."
        )

    return GptReviewResult(ok=True, review=review, raw_response=raw_text)
