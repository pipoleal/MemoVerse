# MemoVerse AI Orchestrator

Automatiza a **comunicação** entre Claude (implementação) e GPT (revisão) para o
desenvolvimento do MemoVerse. Não automatiza autoridade: toda aprovação final
continua sendo humana, via um menu interativo no terminal.

```
Claude  = implementação (via `claude` CLI, não commita/pusha/faz deploy)
GPT     = revisão crítica do que o Claude fez (via API da OpenAI)
Orquestrador = estado + comunicação entre os dois
Você    = decisão final (aprovar / pedir correção / revisar de novo / rejeitar / parar)
```

## Por que funciona assim (decisões da investigação inicial)

- **Como "Claude" é invocado:** este ambiente já roda Claude através da CLI oficial
  `claude` (Claude Code), já autenticada. O orquestrador reutiliza essa mesma
  infraestrutura chamando `claude -p "<tarefa>" --output-format json
  --permission-mode <modo>` — o modo não-interativo oficial e documentado da
  própria CLI, feito exatamente para automação. Não existe (e não foi criada)
  uma segunda integração via API do Anthropic — não havia `ANTHROPIC_API_KEY`
  configurada separadamente, e criar uma seria duplicar autenticação
  desnecessariamente.
- **Como "GPT" é invocado:** SDK oficial `openai` (Python), Chat Completions
  API com `response_format: json_object`. Requer sua própria `OPENAI_API_KEY`
  em `.env` (nunca compartilhada com o Claude, nunca hardcoded).
- **Memória compartilhada:** `docs/ai/*.md` na raiz do repositório — arquivos
  Markdown simples, lidos pelo Claude via suas próprias ferramentas de leitura
  de arquivo, e injetados diretamente no prompt enviado ao GPT (que não tem
  acesso ao sistema de arquivos). Atualize esses arquivos manualmente conforme
  o projeto evolui.

## Instalação

```powershell
cd tools/ai-orchestrator
python -m venv .venv        # opcional, mas recomendado
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edite .env e preencha OPENAI_API_KEY
```

Requer também que o comando `claude` esteja no PATH (já está, se você está
lendo isso a partir de uma sessão do Claude Code).

## Uso

**Sempre rode o autoteste primeiro, antes de usar em uma tarefa real:**

```powershell
python orchestrator.py selftest
```

Isso executa uma tarefa fictícia e somente-leitura ("leia o README e descreva
em 2 frases") para validar toda a cadeia (invocação do Claude, parsing do
relatório, checagem de diff do git, revisão do GPT se configurada, e o menu
de aprovação humana) sem tocar em nenhum arquivo real do MemoVerse.

Depois disso:

```powershell
python orchestrator.py run "Corrija o bug de carregamento infinito em PublicExperienceView.tsx descrito em docs/ai/CURRENT_STATE.md"
python orchestrator.py list
python orchestrator.py resume 20260816-143000-corrija-o-bug
```

## O que este orquestrador NUNCA faz

- Nunca roda `git add`, `git commit`, `git push`, `git reset`, `git checkout .`
  ou qualquer comando destrutivo/de publicação (`git_safety.py` é somente leitura).
- Nunca decide sozinho que uma implementação está pronta — só um humano
  escolhendo "[1] APROVAR" no menu marca uma tarefa como concluída.
- Nunca esconde do humano se o Claude, apesar da instrução explícita,
  acabou commitando algo — isso é detectado (comparando `git rev-parse HEAD`
  antes/depois) e mostrado com destaque antes do menu de aprovação.
- Nunca envia sua chave da OpenAI para o Claude, nem qualquer credencial para
  o GPT (o GPT só recebe texto: relatório, diff, contexto do projeto).

## Camadas de segurança (revisão de 2026-08-16)

Uma revisão de segurança encontrou e corrigiu 3 problemas reais nesta
integração. As camadas abaixo existem por causa disso — ver
`security_tests.py` para a prova executável de cada uma:

1. **Isolamento da `OPENAI_API_KEY`.** `subprocess.run()` sem `env=`
   explícito herda o ambiente inteiro do processo pai — isso fazia o
   processo `claude` (e qualquer `bash` que ele rodasse) enxergar a chave da
   OpenAI. Corrigido: `claude_runner.build_sanitized_claude_env()` monta uma
   cópia do ambiente removendo tudo que começa com `OPENAI_` antes de
   invocar o `claude`, e esse é o `env=` efetivamente passado ao
   `subprocess.run`. O restante do ambiente (PATH, credenciais do próprio
   Claude Code, etc.) é preservado.
2. **Bloqueio técnico de operações perigosas.** Além da instrução em texto
   (`NEVER_COMMIT_INSTRUCTION`, que continua valendo), toda invocação do
   Claude agora passa `--disallowedTools` com padrões que a própria CLI do
   Claude Code recusa executar **antes** do comando rodar —
   `claude_runner.DISALLOWED_TOOL_PATTERNS` cobre `git commit/push/reset/
   clean/checkout/rm/merge/rebase`, invocações comuns de `manage.py migrate`,
   e alguns comandos de deploy conhecidos (`docker compose up`, `vercel`,
   `npm run deploy`). **Isso é defesa em profundidade, não uma garantia
   absoluta** — o casamento é por padrão de string no comando Bash; uma
   forma de invocar o mesmo programa que não bata com nenhum padrão listado
   não seria pega por esta camada (ficaria só com a instrução em texto + a
   detecção pós-fato de `commits_created` em `git_safety.py`).
3. **Scanner de segredos antes do GPT.** `secrets_scanner.py` varre as
   linhas adicionadas do `git diff` (padrões locais e determinísticos: sk-*,
   AKIA*, gh*_*, xox*-*, blocos `-----BEGIN...PRIVATE KEY-----`, JWTs,
   atribuições genéricas tipo `api_key = "..."`, etc. — sem dependências
   externas). Se algo bater, o diff **não é enviado à API da OpenAI**; a
   etapa de revisão do GPT é pulada e um aviso é mostrado ao humano antes do
   menu de aprovação. O `.env` em si já nunca aparece no diff (ver seção
   acima) — isto cobre o caso de uma credencial acidentalmente hardcoded em
   um arquivo rastreado.

Nenhuma dessas correções alterou a máquina de estados nem removeu o menu de
aprovação humana — só adicionaram camadas antes dele.

## Limites de segurança contra loop infinito

`MAX_GPT_REVIEWS` e `MAX_CORRECTION_ATTEMPTS` (configuráveis em `.env`,
padrão 3 cada) impedem que uma tarefa fique presa em um ciclo
Claude → GPT → correção → Claude → GPT... sem fim. Ao atingir o limite, a
tarefa vai para o estado `BLOCKED` e exige intervenção humana direta (fora
do orquestrador).

## Máquina de estados

```
IDLE → TASK_RUNNING → IMPLEMENTATION_READY → GPT_REVIEW → WAITING_HUMAN_APPROVAL
                                                                  │
                        ┌─────────────────┬───────────┬──────────┼───────────┐
                     APROVAR      PEDIR CORREÇÃO   REVISAR   REJEITAR      PARAR
                        │                 │        NOVAMENTE     │           │
                    COMPLETED   CORRECTION_REQUIRED  (GPT_REVIEW) BLOCKED  (estado salvo,
                                       │                                   retomável)
                                  (volta pro topo, ou BLOCKED se
                                   limite de tentativas foi atingido)
```

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `orchestrator.py` | CLI, laço principal, menu de aprovação humana |
| `claude_runner.py` | Invoca `claude -p ...` como subprocesso, extrai o relatório JSON |
| `gpt_reviewer.py` | Chama a API da OpenAI para revisar o relatório + diff |
| `git_safety.py` | Checagens **somente leitura** de git (snapshot, diff, pré-voo) |
| `state_store.py` | Persiste o estado de cada tarefa em `state/*.json` (gitignored) |
| `schemas.py` | Formatos dos relatórios trocados entre Claude, GPT e humano |
| `secrets_scanner.py` | Varre o diff por padrões de credencial antes de liberar o envio ao GPT |
| `security_tests.py` | Testes que provam as garantias de segurança acima (`python security_tests.py`) |

## Riscos conhecidos / limitações desta primeira versão

- `CLAUDE_PERMISSION_MODE=acceptEdits` (padrão) faz o Claude aceitar edições
  de arquivo automaticamente, sem parar para confirmação — isso é necessário
  para rodar sem supervisão, mas significa que você está confiando no
  julgamento do Claude para essa tarefa específica. Se preferir aprovar cada
  ação manualmente, mude para `manual` no `.env` (mais lento, mais seguro).
- `--disallowedTools` (ver seção "Camadas de segurança" acima) cobre os
  padrões de comando mais óbvios, mas é casamento de string — não é uma
  sandbox. Continua sendo defesa em profundidade junto com a instrução em
  texto e a detecção pós-fato de commit, não uma garantia matematicamente
  completa.
- O parsing do relatório do Claude depende de ele terminar a resposta com um
  bloco ```json corretamente formatado. Se ele não fizer isso, o orquestrador
  detecta e sinaliza isso ao humano em vez de inventar um relatório.
- O scanner de segredos é local, baseado em regex, e propositalmente simples
  — pode não pegar um formato de credencial fora dos padrões listados em
  `secrets_scanner.py`. Não é um substituto para revisão humana do diff.
- Este v1 é um CLI simples de laço único (uma tarefa por vez). Não há fila,
  não há execução paralela de múltiplas tarefas.
