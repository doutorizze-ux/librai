# Product Requirements Document (PRD) - Sinaliza AI

## 1. Introdução e Visão Geral
O **Sinaliza AI** é uma plataforma de acessibilidade baseada em Inteligência Artificial projetada para traduzir a Língua Brasileira de Sinais (Libras) para português (texto e voz), bem como facilitar a comunicação bidirecional entre pessoas surdas e ouvintes. 

O produto foca em fornecer uma experiência robusta e fluida em cenários críticos (escolas, hospitais, repartições públicas e comércio) operando tanto online quanto offline para termos de acessibilidade essencial.

---

## 2. Personas e Jornadas do Usuário

### Persona 1: Thiago (Surdo, 24 anos)
- **Perfil**: Usuário nativo de Libras, possui baixa fluência em português escrito.
- **Necessidade**: Ir a consultas médicas ou realizar compras sem depender de um intérprete humano físico o tempo todo.
- **Jornada**: Thiago abre o app no "Modo Tradução ao Vivo", posiciona o celular e sinaliza suas dúvidas. O app traduz para voz para o médico. O médico responde falando, e o app transcreve em texto ampliado para Thiago.

### Persona 2: Dra. Sandra (Médica Ouvinte, 42 anos)
- **Perfil**: Não conhece Libras, atende em um hospital público com alta demanda.
- **Necessidade**: Compreender os sintomas descritos por pacientes surdos com rapidez e precisão para realizar diagnósticos corretos.
- **Jornada**: Utiliza o "Modo Conversa" com o app posicionado sobre a mesa para realizar o diálogo interativo durante a consulta.

---

## 3. Requisitos Funcionais (RF)

### 3.1. Modo Tradução ao Vivo (Câmera)
- **RF-1.1**: O app deve capturar vídeo em tempo real e guiar o enquadramento do usuário (verificando iluminação e visibilidade de mãos/rosto/corpo).
- **RF-1.2**: Deve extrair landmarks visuais localmente no dispositivo usando MediaPipe.
- **RF-1.3**: Deve exibir legendas parciais de tradução durante a sinalização e consolidar a frase quando a sinalização terminar.
- **RF-1.4**: Deve reproduzir o texto traduzido em áudio usando o sintetizador nativo de Text-to-Speech (TTS).
- **RF-1.5**: Deve apresentar visualmente a confiança do modelo (sem inventar traduções abaixo de 70% de confiança).
- **RF-1.6**: Permitir que o usuário envie correções textuais para o banco local/nuvem.

### 3.2. Modo Aprender Sinais (Dicionário Educativo)
- **RF-2.1**: Dicionário categorizado (Saudações, Saúde, Emergência, etc.) com busca rápida em português.
- **RF-2.2**: Reprodução de vídeos demonstrativos com controle de velocidade, repetição (loop) e modo espelhado.
- **RF-2.3**: Exercício com a câmera onde o usuário imita o sinal e o app avalia a trajetória e orientação das mãos (com fins puramente pedagógicos).

### 3.3. Modo Conversa (Tela Dividida)
- **RF-3.1**: Interface dividida para diálogo bidirecional (sinalização da pessoa surda traduzida em texto/voz + fala da pessoa ouvinte transcrita em texto ampliado).
- **RF-3.2**: Histórico de conversa em formato de chat com opção de limpar e alterar o tamanho da fonte.

### 3.4. Portal Administrativo (Web)
- **RF-4.1**: Gerenciamento de usuários, permissões (RBAC) e logs de auditoria imutáveis.
- **RF-4.2**: Cadastro e revisão de glosses, variantes regionais e correções enviadas por usuários.
- **RF-4.3**: Painel de visualização de métricas de modelos (matriz de confusão, taxa de rejeição, WER, ECE) e gerenciamento de deploys e rollbacks de modelos.

---

## 4. Requisitos Não Funcionais (RNF)

### 4.1. Desempenho e Latência
- **RNF-1.1**: A latência de inferência para sinais isolados no dispositivo deve ser inferior a 250ms (P95).
- **RNF-1.2**: O pipeline de frames deve implementar *backpressure* dinâmico para não sobrecarregar a CPU de dispositivos antigos.

### 4.2. Funcionamento Offline
- **RNF-2.1**: O app deve possuir um modelo local compacto (ONNX/TFLite) capaz de traduzir um vocabulário essencial offline (alfabeto, números e frases de emergência).

### 4.3. Segurança e Privacidade (LGPD)
- **RNF-3.1**: Minimização de dados: frames de vídeo bruto não devem ser enviados para servidores por padrão (processamento local).
- **RNF-3.2**: O app deve exigir consentimento explícito e separado para o uso comum e para o compartilhamento de contribuições voluntárias (exclusão facilitada a qualquer momento).
- **RNF-3.3**: Criptografia AES-256 para dados armazenados localmente e TLS 1.3 para dados em trânsito.

### 4.4. Acessibilidade
- **RNF-4.1**: O app e o painel administrativo devem estar em estrita conformidade com a diretriz WCAG 2.2 AA (leitores de tela, contraste mínimo de cores 4.5:1, foco claro no teclado, etc.).

---

## 5. Critérios de Aceitação para Produção
1. A tradução deve explicitamente exibir mensagens de erro/limitação em caso de baixa confiança, sem "alucinar" palavras.
2. Nenhum vídeo do usuário deve ser salvo localmente ou enviado sem aceite do consentimento específico e logado.
3. Rollback de modelos no portal administrativo deve ser atômico e executado em menos de 10 segundos.
4. O app deve ser totalmente utilizável com leitores de tela ativos (TalkBack e VoiceOver).
