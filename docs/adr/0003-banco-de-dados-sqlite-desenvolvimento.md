# ADR 0003: Banco de Dados de Desenvolvimento e Mobile

## Status
Aprovado

## Contexto
O Sinaliza AI necessita persistir dados localmente no aplicativo móvel (histórico de conversas, favoritos, configurações de acessibilidade) e o backend necessita gerenciar auditorias, cadastros de glosses, usuários e consentimentos. Configurar um servidor PostgreSQL local de imediato pode criar barreiras de instalação para desenvolvedores ou usuários testando a fundação técnica localmente.

## Decisão
Decidimos utilizar:
1. No **Aplicativo Móvel**: O banco local **Drift** (SQLite reativo para Flutter), que fornece excelente performance de leitura/escrita, suporte a migrations nativas e possibilidade de criptografia transparente via SQLCipher.
2. No **Backend (FastAPI)**: Para o ambiente local de desenvolvimento, configuramos a conexão do ORM SQLAlchemy para criar um banco **SQLite** local (arquivo `.db` local na raiz do projeto do gateway). Para o ambiente de staging/produção, a conexão utilizará variáveis de ambiente para se conectar ao **PostgreSQL** gerenciado, sem alterar o código do ORM.

## Consequências
- **Positivas**:
  - Instalação instantânea: O desenvolvedor/usuário não precisa configurar servidores locais de banco de dados para rodar a base técnica.
  - Portabilidade: Os arquivos de banco local podem ser limpos ou inspecionados facilmente.
- **Negativas**:
  - Limitações do SQLite quanto a tipos de dados específicos (como arrays nativos ou JSON avançado no SQLAlchemy). Mitigamos isso usando tipos genéricos compatíveis ou conversões de strings JSON via Pydantic.
