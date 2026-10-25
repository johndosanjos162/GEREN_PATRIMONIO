# Patrimônio 360 Private Edition

Site HTML/CSS/JavaScript de gerenciamento patrimonial com interface tecnológica, painel interno, login exclusivo e armazenamento no Supabase protegido por RLS. Sem botão de cadastro.

## Instalação (Supabase + GitHub Pages)

1. No Supabase, abra SQL Editor e execute `supabase_setup.sql`.
2. Em Authentication → Providers → Email, desative **Allow new users to sign up** (desativar cadastros públicos). Se a configuração estiver em outra tela, procure a opção de permitir cadastros.
3. Em Authentication → Users, crie manualmente a sua conta autorizada (e-mail e senha). Não envie sua senha a ninguém.
4. Em Project Settings → API, copie **Project URL** e **anon/publishable key**. Insira em `window.P360_CONFIG` no começo de `index.html`.
5. **Nunca** insira `service_role`/secret key no HTML. A chave publicável é adequada apenas com RLS configurada.
6. Faça upload de `index.html` para um repositório e habilite GitHub Pages em Settings → Pages → Deploy from a branch → main /root.
7. Acesse sua página por HTTPS e faça login. O site usa o Supabase para salvar as informações entre dispositivos.

## Dados anteriores

Os dados que estavam salvos na versão local antiga **não são migrados automaticamente**. Abra a versão antiga no mesmo navegador, faça **Backup JSON** e importe o JSON pela página **Relatórios** após entrar no novo site. Guarde esse backup em local seguro.

## Segurança e limites

- O login é **real**, validado pelo Supabase Auth. Não há senha embutida nem botão de criar conta.
- A tabela com RLS restringe leitura e gravação ao usuário autenticado. Uma conta autorizada é criada manualmente pelo administrador no painel do Supabase.
- O código fonte HTML/CSS/JS é público em sites estáticos, mas os dados exigem autenticação e as políticas RLS.
- Os dados não são criptografados ponta a ponta; a segurança depende das configurações de acesso, RLS e conta Supabase. Ative MFA se disponível e use senha exclusiva.
- Se a sincronização apresentar **Erro ao salvar**, exporte backup antes de sair. Não use a versão sem configurar o SQL.
- Não há recuperação ou redefinição de senha dentro do site. Gerencie usuários autorizados pelo Supabase.
