# Patrimônio 360 Web — Disciplina Financeira

## Instalação
1. Faça backup do index.html atualmente publicado e exporte um JSON no site.
2. No novo `index.html`, substitua os dois placeholders `SUPABASE_URL` e `SUPABASE_ANON_KEY` pelos valores públicos já usados no site anterior. Nunca use service_role ou secret.
3. Publique `index.html` na raiz do GitHub Pages. Não é necessário executar SQL novo: utiliza a mesma tabela `patrimonio360_data` e o mesmo login.
4. Acesse o menu **Disciplina financeira**, defina os percentuais de corte por categoria e revise os motivos.
5. Vá a **Relatórios**, escolha **Baixar PDF completo**, ou use **Relatório disciplinar PDF** na nova área.

## Cálculos
- Gastos de referência = lançamentos variáveis do mês atual + gastos fixos recorrentes.
- Economia projetada = gastos x percentual definido / 100.
- Saldo projetado = saldo registrado + economia projetada.
- Registro de corte confirmado **não altera** transações ou saldos. A economia efetiva deve ser verificada nos meses seguintes.
- O prazo estimado para metas assume aporte constante e não considera retorno de aplicações, inflação, custos ou impostos.
- As classificações de despesas fixas são sugeridas pelo texto da descrição. Confira-as.

## Relatórios PDF
Exportação client-side via jsPDF CDN. Exige internet para carregar a biblioteca, mas não envia os dados para um serviço externo para criação do PDF. O arquivo gerado contém dados financeiros sensíveis.

## Notas de segurança
A senha é validada pelo Supabase Auth; nunca insira sua senha no HTML. Use RLS na tabela `patrimonio360_data`. Os dados do plano de corte ficam armazenados no campo JSON `payload._disciplina`; portanto não é preciso alterar o esquema SQL.
