# Patrimônio 360 Web

Site de gestão patrimonial pessoal, feito em um único `index.html` com HTML, CSS e JavaScript puros.

## Como iniciar

1. Abra `index.html` em seu navegador, sem instalar dependências.
2. Para publicar: crie um repositório no GitHub, envie o `index.html` para a raiz e habilite **Settings > Pages > Deploy from a branch**, na branch principal e pasta `/ (root)`.
3. Cadastre bens, investimentos, dívidas, receitas, despesas, gastos fixos, contas e metas.
4. Faça backup em **Relatórios > Exportar JSON**.

## Importante

- Dados ficam no `localStorage` do navegador, sem sincronização ou login.
- Não coloque dados financeiros sensíveis em navegador compartilhado.
- Navegadores diferentes ou limpeza de dados podem apagar os registros; mantenha backups JSON fora do navegador.
- É um aplicativo independente, não importa automaticamente os dados antigos do Streamlit/Supabase.
- Não se conecte a um banco de dados público usando chave `service_role` em JavaScript de navegador.
- Para integração futura com Supabase: autenticação Supabase Auth, permissões por usuário e RLS obrigatórias.
- Cálculos de fluxo mensal são estimativas de planejamento; gastos fixos são tratados como mensais e somados a cada mês no gráfico.
- O patrimônio não duplica investimentos: ativos e investimentos são cadastros distintos. Não registre a mesma aplicação nas duas seções.
- Rentabilidade e projeções não contemplam inflação, tributos ou taxas.

## Arquivos

- `index.html`: código completo do site (estilos, telas, banco local, cálculos, exportação).

## Recursos

- Painel principal com gráficos Canvas, indicadores e contas pendentes.
- Cadastros com criação, edição, pesquisa e exclusão.
- Controle de vencimentos, status de pagamento e metas.
- Simulador de juros compostos.
- Exportação CSV por módulo, backup/restauração JSON.
- Responsivo para desktop e celular.
