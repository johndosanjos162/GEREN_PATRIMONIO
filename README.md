# Patrimônio 360

Um **novo aplicativo Streamlit** para administrar patrimônio pessoal. É uma reconstrução visual e funcional, não apenas um novo tema do Invest Control Pro antigo.

## Funcionalidades

- **Visão geral:** patrimônio líquido, ativos, investimentos, dívidas, saldo estimado do mês e próximas contas.
- **Meu patrimônio:** cadastro, categorização, distribuição e exclusão de bens.
- **Dívidas:** saldo devedor, juros, parcelas e prioridade por taxa.
- **Investimentos:** aplicações, classes, valor investido, valor atual, distribuição e atualização de avaliação.
- **Fluxo de caixa:** lançamento de receitas e despesas com gráfico de 12 meses.
- **Contas e orçamento:** gastos fixos, contas a pagar e situação de pagamento.
- **Metas financeiras:** cadastro, evolução e atualização de valores.
- **Simulador:** juros compostos, aporte mensal e exportação CSV.
- **Relatórios e dados:** PDF, CSV, backup das tabelas.

## Instalação local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ao iniciar sem configuração, cria-se `patrimonio360.db` **no diretório corrente**. Guarde esse arquivo para fazer backups. Em hospedagens temporárias (por exemplo, servidores que reiniciam com disco descartável), prefira Supabase para evitar perda de dados.

## Proteção por senha

Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e defina `APP_PASSWORD` com uma senha forte. **Nunca publique `secrets.toml` no GitHub.** Alternativamente, use a variável de ambiente `APP_PASSWORD`. Para um app exposto na internet, configure a senha antes da publicação. Este é um bloqueio simples para uso pessoal, **não um sistema multiusuário de autenticação**.

## Usar Supabase com seus dados anteriores

Configure `SUPABASE_URL` e `SUPABASE_KEY` nos Secrets da hospedagem, junto com `APP_PASSWORD`. A versão nova usa as seguintes tabelas existentes no app anterior:

`ativos`, `passivos`, `carteira_invest`, `metas_financeiras`, `fontes_renda`, `despesas_variaveis`, `gastos_fixos`, `contas_pagar`.

**Não apaga, renomeia nem migra automaticamente tabelas existentes.** Confirme as permissões, políticas de acesso e tipos de colunas do seu Supabase antes de ativar. Se sua tabela exige colunas adicionais obrigatórias ou possui regras específicas, talvez seja necessário adaptá-las. Para usar o modo local, deixe o Supabase sem configuração.

> Segurança: para ambiente público, prefira uma arquitetura de autenticação real com políticas RLS/usuário. Uma chave com privilégios administrativos nunca deve ser exposta em frontend ou em repositório; o uso de uma chave no servidor do Streamlit exige controle rigoroso de acesso.

## Importante sobre o saldo do mês

Saldo estimado = **receitas cadastradas no mês − despesas variáveis cadastradas no mês − total dos gastos fixos cadastrados**. Uma conta a pagar não é deduzida de novo no cálculo para evitar dupla contagem automática. Essa é uma visão de planejamento, não conciliação bancária.

## Limites da versão

- Não consulta saldos reais de corretoras ou bancos.
- Não armazena histórico de valor de mercado de cada ativo, apenas avaliação atual.
- Não calcula tributos, inflação, IOF ou IR no simulador.
- Não contempla todos os módulos do antigo Invest Control Pro (por exemplo, gestão de cortes inteligente e a divisão de aluguel entre pessoas). É um **novo produto focado em patrimônio**.
- Dados do Supabase dependem dos nomes e tipos das tabelas existentes.
