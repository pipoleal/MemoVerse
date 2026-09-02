# MemoVerse Frontend — Regras de Desenvolvimento

## Contexto

O frontend do MemoVerse é uma aplicação Next.js responsável pela interface
de criação, preview, dashboard, checkout e experiências públicas.

Para o contexto geral do produto, funcionalidades existentes, estado do
lançamento e decisões de arquitetura, leia:

../CLAUDE.md

---

## Regras obrigatórias

Antes de modificar qualquer componente:

1. Leia `../CLAUDE.md`.
2. Verifique se a funcionalidade já existe.
3. Procure componentes reutilizáveis antes de criar novos.
4. Não duplicar lógica existente.
5. Não criar novas APIs se uma API existente atender ao caso.
6. Não alterar funcionalidades aprovadas sem necessidade.
7. Manter TypeScript tipado.
8. Preservar responsividade.
9. Não adicionar dependências sem justificar.
10. Fazer alterações pequenas e isoladas.

---

## Estrutura principal

### Experiência

`components/experience/`

Contém o wizard de criação de experiências.

### Preview / experiência pública

`components/experience-view/`

Responsável pela apresentação visual das experiências.

### Universo / Galáxia

`components/universe/`

Contém componentes visuais relacionados ao universo.

Antes de criar qualquer sistema novo de Galáxia, verificar o que já existe
nessa pasta.

### Dashboard

`components/dashboard/`

Responsável pelos dados e interface do dashboard.

### Upload

`lib/mediaUpload.ts`

Responsável pela comunicação relacionada ao upload de mídia.

Não duplicar essa lógica em componentes.

### Experiência pública

`lib/publicExperience.ts`

Centraliza lógica relacionada à experiência pública.

### Draft anônimo

`lib/anonymousDraft.ts`

Responsável pelo estado do draft anônimo no navegador.

---

## Fluxo importante

O fluxo anônimo aprovado é:

Landing
→ Experience
→ Wizard
→ Fotos
→ Carta
→ Preview
→ Cadastro/Login
→ Claim
→ Checkout

Após claim de um draft anônimo:

`/checkout/{draftId}`

Login sem draft pendente:

`/dashboard`

Não alterar esse comportamento sem solicitação explícita.

---

 Upload

O upload utiliza:

Frontend
→ upload-intent
→ URL assinada
→ R2
→ complete

Múltiplos uploads podem ocorrer simultaneamente.

As fotos possuem `sort_order` e `caption`.

O sistema de captions já está implementado.

Não recriar essa funcionalidade.

---

## Loading / UX

Operações assíncronas devem fornecer feedback visual adequado.

Evitar situações em que o usuário não consegue distinguir:

"processando"

de:

"travou".

Não alterar o design visual existente sem necessidade.

---

## Galáxia

Existem componentes existentes em:

`components/universe/`

Antes de implementar Galáxia do Usuário ou Galáxia Viva:

1. verificar os componentes existentes;
2. verificar `star-generator.ts`;
3. verificar APIs existentes;
4. reutilizar o máximo possível;
5. não criar uma segunda implementação do universo.

---

## Antes de finalizar

Executar quando aplicável:

- `npm run build`
- ESLint
- `git diff --check`

Informar:

- arquivos alterados;
- testes executados;
- resultado;
- problemas restantes.

Não fazer commit ou push sem solicitação.
