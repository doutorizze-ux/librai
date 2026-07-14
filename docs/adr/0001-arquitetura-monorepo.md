# ADR 0001: Estrutura do Monorepo

## Status
Aprovado

## Contexto
O projeto Sinaliza AI necessita de múltiplos aplicativos (App móvel Flutter, Painel Web Next.js) e serviços (Gateway FastAPI, serviços de ML). Se desenvolvidos em repositórios separados, haveria duplicação de contratos de API, dificuldades no versionamento de modelos e complexidade extra para configurar o pipeline de CI/CD.

## Decisão
Decidimos utilizar uma estrutura de **Monorepo** organizada em diretórios específicos (`apps/`, `packages/`, `ml/`, `infrastructure/`, `docs/`). 
- As APIs REST/WebSocket serão definidas de forma centralizada em `packages/api-contracts/` usando especificações OpenAPI.
- A comunicação entre aplicativos e backend utilizará esses esquemas auto-gerados para garantir acoplamento seguro e validação estática de dados.

## Consequências
- **Positivas**:
  - Código unificado facilitando o rastreio de alterações transacionais (ex: alterar um campo da API e corrigir simultaneamente no Flutter, Next.js e FastAPI em um único commit).
  - Centralização de scripts de infraestrutura, Dockerfiles e manifestos K8s.
  - Facilidade de compartilhamento de tipos de dados de inferência de ML.
- **Negativas**:
  - Tamanho inicial do repositório pode crescer se não for configurado o descarte de pacotes pesados ou versionamento adequado de grandes arquivos binários (resolvido usando Git LFS e DVC para modelos e datasets).
