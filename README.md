# Invest Control Pro — atualização de interface e organização

## O que foi mantido
- 9 abas e respectivos cálculos, simuladores, fluxo de login, relatórios PDF e operações Supabase.
- Mesmos nomes de tabelas e colunas; não requer migração SQL.
- Compatibilidade com as credenciais antigas **sem a senha em texto aberto no código**.

## Melhorias
- Interface responsiva, rolagem horizontal das abas e tipografia mais legível.
- Cabeçalho executivo, navegação compacta, melhor contraste, foco de teclado.
- Histórico de despesas com filtro por período, busca e subtotal visual (não altera totais dos cálculos originais).
- Autenticação configurável com `APP_USERNAME`, `APP_PASSWORD` ou `APP_PASSWORD_SHA256` via Secrets ou variáveis de ambiente.
- Aviso visível quando a integração Supabase não está configurada.

## Instalação
1. `pip install -r requirements.txt`
2. Coloque `config.toml` em `.streamlit/config.toml` (já incluso).
3. Configure Secrets na plataforma de hospedagem, usando `secrets.toml.example` como modelo. **Nunca publique o arquivo real.**
4. Execute `streamlit run app.py`.

## Cuidados
- Faça backup das tabelas Supabase antes de substituir o app publicado.
- Esta atualização mantém intencionalmente a lógica financeira e seus comportamentos originais.
- O login é um bloqueio básico da interface, **não substitui** políticas RLS do Supabase nem autenticação de usuários no banco.
- Se o projeto usa uma chave privilegiada (`service_role`), não a use para consultas desprotegidas; revise o modelo de acesso.
- O código foi conferido por compilação e consistência estrutural, mas não foi testado com seu banco real.
