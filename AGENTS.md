# Permanent Agent Guidelines - Sinaliza AI

Este arquivo contém as diretrizes permanentes de desenvolvimento e governança para todos os agentes de IA que atuarem neste monorepo. **Não remova ou altere estas regras sem aprovação explícita do usuário.**

---

## 1. Princípios de Desenvolvimento de Software

### 1.1. Arquitetura do Monorepo
- Respeite a divisão de responsabilidades. Não misture lógica de negócios de Machine Learning com o Gateway de APIs ou lógica de UI no Flutter.
- Qualquer alteração em contratos de API deve ser refletida primeiro em `packages/api-contracts/` antes de ser implementada no Next.js (Admin) ou FastAPI (Backend).

### 1.2. Flutter Clean Architecture
- O aplicativo em `apps/mobile/` deve seguir estritamente a Clean Architecture dividida em:
  - `presentation`: Widgets, controladores e gerenciadores de estado (Riverpod). Não insira lógica de negócio diretamente nos widgets.
  - `domain`: Entidades puras e casos de uso (UseCases). Sem dependência de pacotes externos ou frameworks.
  - `data`: Repositórios concretos, datasources (locais/remotos) e mapeamento de modelos.
  - `platform`: Integrações nativas de baixo nível (Câmera, TTS, permissões).

### 1.3. Next.js e Segurança no Servidor
- Não confie em validações puramente do lado do cliente (frontend). Toda autorização de rota deve ser validada nos Server Components ou middlewares.
- Valide todas as entradas de formulários usando esquemas Zod.

---

## 2. Acessibilidade (WCAG 2.2 AA)
- Todos os novos botões ou ações do Flutter devem conter descrições semânticas (`semanticsLabel`) para TalkBack/VoiceOver.
- Elementos clicáveis no celular devem ter dimensões mínimas de 48x48 dp.
- O painel Next.js deve manter suporte completo a navegação por teclado (foco visível) e manter relação de contraste de texto de pelo menos 4.5:1.

---

## 3. Privacidade e Conformidade LGPD
- **Sem Gravação Silenciosa**: Nunca grave áudio ou vídeo em segundo plano. Câmera e microfone devem ter indicadores visuais óbvios de gravação ativa.
- **Descarte Imediato**: Imagens brutas da câmera do usuário capturadas no Flutter devem ser processadas localmente e descartadas na RAM volátil em milissegundos.
- **Minimização**: Landmarks faciais de pose/mãos não devem conter dados biométricos estruturais estáticos que permitam identificação pessoal.

---

## 4. Testes e CI/CD
- Todos os novos endpoints do FastAPI devem ser cobertos por testes unitários/integração usando `pytest`.
- Todos os novos componentes interativos do Next.js devem possuir testes básicos.
- Não desative testes ou ignore erros para fazer compilações passarem.
- Use dados sintéticos ou mocks nas barreiras externas para testes de rede e ML.
