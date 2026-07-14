# Privacy and LGPD Governance - Sinaliza AI

> [!WARNING]
> **RASCUNHO TÉCNICO**: Este documento e as políticas anexas representam diretrizes técnicas de engenharia de software para conformidade com a LGPD e precisam de validação jurídica formal antes do lançamento público.

## 1. Princípios LGPD Aplicados

### 1.1. Minimização de Dados e Privacy by Design
- O **Sinaliza AI** foi projetado para operar localmente no dispositivo. A extração de landmarks (coordenadas geométricas das mãos, face e postura) é realizada na memória volátil do aplicativo.
- O vídeo bruto da câmera do celular **nunca é transmitido ou salvo nos servidores do Sinaliza AI por padrão**. Os frames são descartados imediatamente após a extração dos landmarks geométricos.

### 1.2. Não-Biometria e Privacidade Facial
- Os landmarks faciais extraídos pelo MediaPipe (como contorno de olhos e lábios para expressões não manuais em Libras) são usados **única e exclusivamente para análise de morfologia gestual e expressões gramaticais**.
- O sistema **não realiza reconhecimento facial de identidade** e os dados de landmarks não possuem resolução ou mapeamento estrutural estático que permita identificar a pessoa fisicamente (reconstrução facial estática desabilitada).

---

## 2. Gestão de Consentimento do Usuário
O fluxo de consentimento é explícito, granular e revogável:

1. **Consentimento A (Uso do App)**: Permissão de acesso à câmera para captura local de sinais. Obrigatório para a funcionalidade básica do aplicativo.
2. **Consentimento B (Melhoria do Sistema - Contribuição)**: Opção secundária e totalmente voluntária do usuário para enviar landmarks de sinais mal compreendidos ou vídeos para fins de retreinamento do modelo. O app funciona perfeitamente sem este consentimento.
3. **Revogação Facilitada**: A qualquer momento, nas configurações, o usuário pode desativar o consentimento B e solicitar a exclusão de todas as suas contribuições anteriores.

---

## 3. Direitos do Titular (LGPD) e Requisições
Disponibilizamos endpoints específicos no Backend (`/v1/privacy/*`) para atender as demandas dos titulares:
- **Portabilidade de Dados**: Exportação de todo o histórico de traduções locais e dados de perfil em formato estruturado (JSON/CSV).
- **Exclusão de Dados (Direito ao Esquecimento)**: Deleção atômica de todas as informações vinculadas ao ID do usuário das bases de dados de produção e filas de processamento.
- **Auditoria de Consentimento**: Mapeamento e versionamento das assinaturas de termos e políticas aceitas pelo usuário.

---

## 4. Política de Retenção de Dados Técnicos

| Tipo de Dado | Destino / Armazenamento | Prazo de Retenção | Método de Descarte |
| :--- | :--- | :--- | :--- |
| Frames de Vídeo Bruto | Memória RAM local (Volátil) | Descarte imediato (<1s) | Sobrescrita de buffer |
| Landmarks Geométricos (Sem Consentimento B) | Memória RAM local (Volátil) | Descarte imediato (<1s) | Sobrescrita de buffer |
| Histórico de Tradução | SQLite Local (Criptografado) | Até que o usuário apague ou desinstale o app | Deleção lógica/física local |
| Landmarks Geométricos (Com Consentimento B) | S3 Privado Criptografado | 90 dias após auditoria linguística | Exclusão física permanente |
