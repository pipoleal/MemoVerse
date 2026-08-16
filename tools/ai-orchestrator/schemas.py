"""Structured report shapes exchanged between Claude, GPT, and the human.

These are plain dicts (not a validation library) to keep the tool
dependency-free beyond the OpenAI SDK. `extract_json_block` pulls the last
fenced ```json block out of free-form model text.
"""
from __future__ import annotations

import json
import re

CLAUDE_REPORT_SCHEMA_DESCRIPTION = """
Ao terminar a implementação (ou ao concluir que está bloqueado), termine sua
resposta final com um bloco de código ```json contendo EXATAMENTE estas chaves:

{
  "status": "done" | "blocked" | "partial",
  "summary": "resumo em 1-3 frases do que foi feito ou por que está bloqueado",
  "files_changed": ["lista", "de", "caminhos", "relativos", "de", "arquivos", "alterados"],
  "tests_run": "descrição do que foi testado/executado e o resultado, ou null se nada foi testado",
  "blockers": ["lista de bloqueios encontrados (credenciais faltando, etc.), vazio se nenhum"],
  "notes_for_reviewer": "qualquer coisa que o revisor (outra IA) deveria saber para avaliar esta mudança"
}

Esse bloco JSON deve ser a ÚLTIMA coisa na sua resposta.
""".strip()

GPT_REVIEW_SCHEMA_DESCRIPTION = """
Responda EXCLUSIVAMENTE com um objeto JSON (nenhum texto fora dele) com estas chaves:

{
  "verdict": "approve" | "request_changes" | "reject",
  "summary": "resumo em 1-3 frases da sua avaliação",
  "issues": [
    {"severity": "high" | "medium" | "low", "description": "string", "file": "caminho ou null"}
  ],
  "suggested_correction_prompt": "instrução clara e acionável a ser reenviada para o Claude corrigir, ou null se verdict for approve"
}
""".strip()


def extract_json_block(text: str) -> dict | None:
    """Extract the last ```json ... ``` fenced block from `text` and parse it.

    Returns None if no valid JSON block is found — callers must treat this
    as "the model did not produce a structured report" rather than guessing.
    """
    matches = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not matches:
        # Fall back to: the whole text is JSON (GPT is asked to respond with
        # only JSON, no fence).
        try:
            return json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            return None
    for candidate in reversed(matches):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def empty_claude_report(reason: str) -> dict:
    return {
        "status": "blocked",
        "summary": reason,
        "files_changed": [],
        "tests_run": None,
        "blockers": [reason],
        "notes_for_reviewer": "Nenhum relatório JSON estruturado foi encontrado na saída do Claude.",
    }


def empty_gpt_review(reason: str) -> dict:
    return {
        "verdict": "request_changes",
        "summary": reason,
        "issues": [{"severity": "high", "description": reason, "file": None}],
        "suggested_correction_prompt": None,
    }
