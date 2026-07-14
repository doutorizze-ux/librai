# Accessibility Standards (WCAG 2.2 AA) - Sinaliza AI

Como uma ferramenta voltada para acessibilidade comunicativa, o **Sinaliza AI** deve cumprir rigorosamente as normas **WCAG 2.2 nível AA** no aplicativo móvel e no painel web.

---

## 1. Diretrizes para o App Flutter

### 1.1. Árvore de Semântica e Leitores de Tela (TalkBack/VoiceOver)
- **Widgets Semânticos**: Botões que contêm apenas ícones devem ser envolvidos por um widget `Semantics` ou usar a propriedade `semanticsLabel` do widget `IconButton`.
  ```dart
  IconButton(
    icon: Icon(Icons.volume_up),
    semanticsLabel: 'Reproduzir tradução em voz',
    onPressed: _speakTranslation,
  );
  ```
- **Ordem de Leitura**: O aplicativo deve possuir fluxo semântico lógico. Use `Semantics(sortKey: OrdinalSortKey(1.0))` se for necessário reorganizar a ordem de navegação dos leitores de tela em layouts complexos.

### 1.2. Áreas de Toque (Touch Targets)
- Todos os botões e áreas interativas devem possuir no mínimo **48x48 pixels de área clicável física** (diretriz Android/iOS), mesmo que o ícone visual seja menor.

### 1.3. Redimensionamento de Texto e Layouts Dinâmicos
- **Sem Altura Fixa em Contêineres**: Evitar `Container(height: 50)` em cards com texto. Se o usuário aumentar o tamanho da fonte do sistema para 200%, o texto deve quebrar linha e o card deve expandir dinamicamente para evitar cortes de palavra.
- Usar `MediaQuery.textScaleFactorOf(context)` para ajustar o layout se necessário, mas preferir layouts baseados em `Wrap` e `Flex/Column/Row` flexíveis.

### 1.4. Não depender unicamente de Cores
- Para indicar o estado da tradução ou a confiança do modelo, não use apenas círculos coloridos (vermelho/verde). Utilize ícones descritivos e textos de apoio (ex: "Confiança: Baixa" com ícone de alerta).

---

## 2. Diretrizes para o Painel Next.js

### 2.1. Navegação por Teclado e Foco Visível
- **Foco Claro**: Todos os elementos interativos (botões, links, inputs) devem ter um contorno visível (focus outline) quando navegados pelo teclado (Tab). **Nunca remover o contorno com `outline: none` sem criar um estado de foco alternativo**.
- **Acessibilidade de Formulários**: Todo `input` deve ter uma tag `<label>` associada explicitamente usando `htmlFor` (ou `id` correspondente).

### 2.2. HTML Semântico e Estrutura de Títulos
- Utilizar apenas **um único `<h1>` por página** correspondente ao cabeçalho principal.
- Utilizar elementos estruturais do HTML5 (`<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`) em vez de divs genéricas.

### 2.3. Contraste de Cores
- Relação de contraste mínima de **4.5:1** para texto normal e **3:1** para texto grande (acima de 18pt ou negrito de 14pt) contra o fundo.

---

## 3. Processo de Validação de Acessibilidade
1. **Verificação Automatizada**: Integração do scanner `axe-core` nos testes do Playwright do Next.js e uso do `flutter test` com analisador de semântica.
2. **Testes Manuais**: Executar navegação de olhos vendados no app usando TalkBack (Android) e VoiceOver (iOS) nas telas de tradução e no dicionário.
3. **Painel de Controle de Acessibilidade**: O app deve conter uma tela de configurações que permita forçar o modo de alto contraste e desativar animações (respeitando a configuração de movimento reduzido do sistema operacional).
