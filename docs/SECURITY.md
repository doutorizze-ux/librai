# Security Policy and Threat Model (STRIDE) - Sinaliza AI

## 1. Diretrizes de Segurança Geral
A segurança do **Sinaliza AI** baseia-se nos padrões recomendados pelo **OWASP**:
- **OWASP ASVS (Application Security Verification Standard)**: Validação estrita de entradas, codificação de saídas, sessões sem estado de curta duração.
- **OWASP API Security**: Rate limiting por IP/API key, autenticação baseada em tokens protegidos, verificação contínua de permissões no escopo vertical e horizontal.
- **OWASP MASVS (Mobile Application Security Verification Standard)**: Proteção de dados locais com chaves do sistema (Android Keystore / iOS Keychain), proteção contra Engenharia Reversa (ofuscação) e comunicação TLS Pinning.

---

## 2. Autenticação, Autorização e Gestão de Segredos
- **Protocolo**: OAuth 2.1 com OpenID Connect (OIDC).
- **Access Tokens**: JWT auto-contidos de curta duração (15 minutos).
- **Refresh Tokens**: Armazenados em HTTPOnly Cookies seguros com rotação obrigatória no backend.
- **MFA (Autenticação de Múltiplos Fatores)**: Obrigatória para todos os usuários com acesso ao Portal Administrativo.
- **Cofre de Segredos (Secrets Management)**: Tokens de API, chaves privadas de modelos e credenciais de banco são armazenados em um cofre seguro (e.g., HashiCorp Vault / AWS Secrets Manager) e injetados via variáveis de ambiente no container. **Nunca comitar segredos no Git**.

---

## 3. Modelagem de Ameaças (STRIDE)

| Categoria STRIDE | Ameaça Identificada | Mitigação Aplicada no Sinaliza AI |
| :--- | :--- | :--- |
| **S**poofing (Falsificação) | Acesso não autorizado ao Portal Administrativo fingindo ser um auditor/especialista. | Implementação de MFA obrigatório e verificação de IP/tokens via middleware no Next.js Server Side. |
| **T**ampering (Adulteração) | Modificação maliciosa de arquivos de modelos (ONNX/TFLite) em trânsito ou no dispositivo. | Assinatura digital de cada modelo com chave privada no backend. O app móvel valida o hash SHA-256 e a assinatura antes de carregar o modelo. |
| **R**epudiation (Repúdio) | Alteração não autorizada de glosses ou modelos no Model Registry sem rastro de auditoria. | Criação de tabela de logs de auditoria imutável (sem API de modificação ou exclusão). |
| **I**nformation Disclosure | Vazamento de dados de conversas privadas ou landmarks que revelem a identidade do usuário. | Minimização de dados: landmarks não carregam características faciais estruturais (apenas landmarks móveis). Vídeos nunca são armazenados por padrão. |
| **D**enial of Service | Inundação de requisições de inferência via WebSockets derrubando os serviços de IA. | Rate limiting no nível do Nginx/WAF e backpressure no WebSocket fechando conexões excedentes. |
| **E**levation of Privilege | Usuário comum manipulando chamadas de API para aprovar modelos ou alterar permissões de admin. | RBAC estrito verificado no backend FastAPI (Decorators de role-checking em todas as rotas `/admin/*`). |

---

## 4. Segurança Específica de Machine Learning (ML)
- **Ataques de Inversão de Modelo (Model Inversion)**: Impedir que agentes maliciosos reconstruam o rosto/corpo dos usuários a partir das respostas do modelo. Mitigamos isso restringindo a saída do modelo a tokens de glosses e português estruturado, ocultando as saídas brutas de probabilidade de classes.
- **Envenenamento de Dataset (Dataset Poisoning)**: As contribuições voluntárias de usuários finais nunca entram automaticamente no conjunto de treino. Passam por um pipeline isolado com dupla revisão de intérpretes de Libras antes de serem aprovadas para o dataset oficial.
- **Assinatura de Artefatos**: O pipeline de CI assina os pesos dos modelos exportados. O cliente móvel rejeita a execução de qualquer binário de inferência que não possua a assinatura digital verificável da chave pública embutida no app.
