# Patrimônio 360 — Quantum Finance

Atualização do `index.html` original, preservando os módulos, login Supabase Auth e armazenamento da tabela `public.patrimonio360_data` (`payload` JSONB).

## Instalação

1. No site atualmente publicado, entre em **Relatórios → Exportar JSON** e salve uma cópia do histórico.
2. Guarde também uma cópia do seu `index.html` atual.
3. Abra este `index.html` e preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY` com os valores *públicos* do projeto atual. Não compartilhe nem inclua senha ou `service_role` no HTML.
4. Publique o arquivo na raiz do GitHub Pages e faça login com seu usuário existente.
5. Teste um lançamento em **Despesas** e outro em **Contas a pagar**. Confira a mensagem de sincronização com Supabase antes de sair.

**Banco de dados:** a versão mantém a mesma tabela e o mesmo payload. Não requer SQL adicional. Os campos opcionais adicionados aos registros antigos ficam dentro do JSON já usado pelo site.

## Novidades

- Dashboard de sete indicadores com identidade visual tecnológica e cartões de emblemas.
- Filtro por **ano, mês e categoria** e navegação por competência histórica.
- Gráfico de rosca interativo, fluxo dos últimos 12 meses, comparação de cortes e curva de saldo mensal; detalhes por categoria.
- Gastos fixos recebem campos opcionais de categoria, início e fim, permitindo delimitar sua presença nas séries históricas.
- Contas marcadas como pagas recebem a data do pagamento; antigas sem data usam vencimento **apenas como aproximação visual**.
- Os relatórios PDF incluem lançamentos do mês selecionado, barras de gastos por categoria e comparação de 12 meses, além das seções anteriores.
- Motor de cortes permanece controlado por você. Ação confirmada **não comprova economia financeira realizada**; compare despesas efetivas no período seguinte.

## Cuidados de precisão

- O saldo do mês é uma estimativa de lançamentos informados, não conciliação automática com banco.
- Contas a pagar não são somadas às despesas para evitar duplicação; registre despesas efetivas separadamente quando necessário.
- Os dados históricos de **patrimônio** não podem ser reconstruídos apenas a partir dos valores atuais de bens e dívidas. O gráfico histórico entregue é de **saldo do fluxo mensal**, claramente identificado.
- Gastos fixos legados sem data de início são tratados como recorrentes em todos os períodos e o dashboard avisa que há estimativas.
- O valor de reserva é obtido de bens classificados como **Reserva**. Não inclui automaticamente contas de investimento; classifique os registros conforme sua realidade e evite duplicar um mesmo ativo entre bens e investimentos.
- Bibliotecas externas de Supabase, ECharts e jsPDF exigem internet; gráficos interativos mostram aviso se ECharts estiver indisponível.
- O sistema não possui integração bancária automática. Recomendamos manter backups regulares do JSON.

## Validação

- Sintaxe JavaScript validada com Node.js.
- Testes com sessão autenticada e dados reais no Supabase e verificação visual no navegador **não foram realizados** neste ambiente. Faça os testes antes de substituir definitivamente seu site em produção.
