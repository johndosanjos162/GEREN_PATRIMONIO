"""Patrimônio 360 — gestão patrimonial pessoal com Streamlit.
Banco SQLite local por padrão; Supabase opcional para persistência em nuvem.
"""
import os
import io
import sqlite3
import calendar
from datetime import date, datetime
from pathlib import Path
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(page_title="Patrimônio 360", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

C = {"bg":"#090F1C", "surface":"#111C2D", "surface2":"#17263C", "line":"#283A52", "text":"#F0F5FC", "muted":"#9DB0C7", "blue":"#55A8FF", "teal":"#35D3B8", "red":"#FF7283", "gold":"#F5BF67"}
PALETTE = [C['blue'], C['teal'], C['gold'], '#AD93FA', '#FF8E76', '#7ECAFF']
CATEGORIAS = ["Moradia", "Alimentação", "Transporte", "Saúde", "Educação", "Lazer", "Assinaturas", "Impostos", "Outros"]
ATIVO_TIPOS = ["Imóvel", "Veículo", "Conta bancária", "Reserva", "Bem pessoal", "Negócio", "Outros"]
INV_CLASSES = ["Renda fixa", "Ações", "Fundos imobiliários", "ETFs", "Tesouro Direto", "Previdência", "Outros"]

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], [data-testid="stApp"]{font-family:'DM Sans',sans-serif;color:#F0F5FC}
.stApp{background:radial-gradient(ellipse at 88% 5%,#173255 0,transparent 35%),#090F1C}
.block-container{max-width:1490px;padding-top:2rem;padding-bottom:5rem}
[data-testid="stSidebar"]{background:#0E1929;border-right:1px solid #273950}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem}
[data-testid="stSidebar"] label{font-size:0.88rem}
h1,h2,h3{letter-spacing:-.035em;color:#F0F5FC!important}
h1{font-size:2.05rem!important;font-weight:750!important}
h2{font-size:1.35rem!important}
[data-testid="stMetric"]{background:linear-gradient(145deg,#17283e,#101b2c);padding:17px 18px;border:1px solid #2c4058;border-radius:16px;min-height:127px}
[data-testid="stMetricLabel"]{color:#9DB0C7!important}
[data-testid="stMetricValue"]{color:#F0F5FC!important;font-size:1.6rem!important}
[data-testid="stMetricDelta"]{color:#35D3B8}
[data-testid="stForm"], [data-testid="stExpander"]{background:#111C2D;border:1px solid #283A52;border-radius:16px;padding:10px}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button{background:#3389EF;color:white;border:0;border-radius:10px;font-weight:700}
.stButton button{border-radius:10px}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
.hero{padding:26px 30px;border-radius:22px;border:1px solid #2D4660;background:linear-gradient(115deg,#1B3B5B,#101B2B 75%);margin:0 0 24px}
.hero .kicker{font-size:12px;letter-spacing:1.6px;text-transform:uppercase;color:#7AD9EE;font-weight:700}
.hero h2{font-size:30px!important;margin:9px 0 6px}
.hero p{color:#B9C9DC;margin:0;font-size:14px}
.brand{font-size:26px;font-weight:800;color:#F1F7FF;line-height:1.4}.brand small{display:block;color:#8FA9C3;font-weight:500;font-size:12px;letter-spacing:1.6px}
.subheading{font-size:13px;color:#9DB0C7;padding:5px 0 14px}
hr{border-color:#243650}
@media(max-width:800px){.block-container{padding:1rem}.hero{padding:20px}.hero h2{font-size:24px!important}}
</style>""", unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def brl(v):
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def pct(v):
    return f"{v:.1f}%".replace('.', ',')


def safe_float(value):
    return float(value) if value is not None else 0.0


# Schema compatível com as tabelas de patrimônio e finanças do aplicativo anterior.
SCHEMAS = {
 "ativos": "id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,categoria TEXT NOT NULL,valor REAL NOT NULL",
 "passivos": "id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,tipo TEXT NOT NULL,valor_total REAL NOT NULL,parcelas_restantes INTEGER DEFAULT 0,juros_mensal REAL DEFAULT 0",
 "carteira_invest": "id INTEGER PRIMARY KEY AUTOINCREMENT,ativo TEXT NOT NULL,classe TEXT NOT NULL,valor_investido REAL NOT NULL,valor_atual REAL NOT NULL,data_aporte TEXT NOT NULL",
 "metas_financeiras": "id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,valor_alvo REAL NOT NULL,valor_atual REAL NOT NULL,prazo_anos INTEGER NOT NULL,categoria TEXT NOT NULL",
 "fontes_renda": "id INTEGER PRIMARY KEY AUTOINCREMENT,descricao TEXT NOT NULL,valor REAL NOT NULL,mes INTEGER NOT NULL,ano INTEGER NOT NULL,tipo TEXT NOT NULL",
 "despesas_variaveis": "id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT NOT NULL,descricao TEXT NOT NULL,categoria TEXT NOT NULL,valor REAL NOT NULL",
 "gastos_fixos": "id INTEGER PRIMARY KEY AUTOINCREMENT,descricao TEXT NOT NULL,valor REAL NOT NULL",
 "contas_pagar": "id INTEGER PRIMARY KEY AUTOINCREMENT,descricao TEXT NOT NULL,valor REAL NOT NULL,vencimento TEXT NOT NULL,pago INTEGER NOT NULL DEFAULT 0,categoria TEXT NOT NULL",
}
ALLOWED = set(SCHEMAS)

@st.cache_resource(show_spinner=False)
def get_store():
    url, key = secret('SUPABASE_URL'), secret('SUPABASE_KEY')
    if url and key:
        from supabase import create_client
        return ('supabase', create_client(url, key))
    path = Path(secret('SQLITE_PATH', 'patrimonio360.db'))
    path.parent.mkdir(parents=True, exist_ok=True)
    # Conexões novas por operação para suportar reexecuções Streamlit.
    with sqlite3.connect(path) as conn:
        for name, definition in SCHEMAS.items():
            conn.execute(f'CREATE TABLE IF NOT EXISTS {name} ({definition})')
        conn.commit()
    return ('sqlite', str(path))


def db_read(table):
    if table not in ALLOWED: raise ValueError('Tabela inválida')
    backend, source = get_store()
    if backend == 'supabase':
        rows = []
        offset = 0
        while True:
            chunk = source.table(table).select('*').range(offset, offset + 999).execute().data or []
            rows.extend(chunk)
            if len(chunk) < 1000: break
            offset += 1000
        return pd.DataFrame(rows)
    with sqlite3.connect(source) as conn:
        return pd.read_sql_query(f'SELECT * FROM {table}', conn)


def db_insert(table, values):
    if table not in ALLOWED: raise ValueError('Tabela inválida')
    backend, source = get_store()
    if backend == 'supabase':
        source.table(table).insert(values).execute()
    else:
        cols = list(values)
        with sqlite3.connect(source) as conn:
            conn.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})', list(values.values()))
            conn.commit()


def db_update(table, item_id, values):
    if table not in ALLOWED: raise ValueError('Tabela inválida')
    backend, source = get_store()
    if backend == 'supabase':
        source.table(table).update(values).eq('id', int(item_id)).execute()
    else:
        with sqlite3.connect(source) as conn:
            conn.execute(f'UPDATE {table} SET {",".join(k+"=?" for k in values)} WHERE id=?', [*values.values(), int(item_id)])
            conn.commit()


def db_delete(table, item_id):
    if table not in ALLOWED: raise ValueError('Tabela inválida')
    backend, source = get_store()
    if backend == 'supabase':
        source.table(table).delete().eq('id', int(item_id)).execute()
    else:
        with sqlite3.connect(source) as conn:
            conn.execute(f'DELETE FROM {table} WHERE id=?', (int(item_id),))
            conn.commit()


def execute(operation, success='Operação realizada.'):
    try:
        operation()
        st.toast(success, icon='✅')
        st.rerun()
    except Exception as error:
        st.error(f'Não foi possível concluir: {error}')


def total(df, field):
    return float(pd.to_numeric(df[field], errors='coerce').fillna(0).sum()) if field in df else 0.0


def chart_style(fig, height=350):
    fig.update_layout(height=height, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#B6C7D9', margin=dict(l=8,r=8,t=30,b=12), legend=dict(orientation='h', y=-.25))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#23364A', zerolinecolor='#23364A')
    return fig


def show_table(df, columns, height=360):
    available = [c for c in columns if c in df.columns]
    if df.empty:
        st.info('Ainda não há registros aqui. Use o formulário para começar.')
    else:
        st.dataframe(df[available], use_container_width=True, hide_index=True, height=min(height, 68 + 39*len(df)))


def remove_record(table, df, display):
    if df.empty or 'id' not in df: return
    with st.expander('Excluir um registro'):
        options = {f"#{int(r['id'])} · {str(r.get(display, 'Registro'))}": int(r['id']) for _, r in df.iterrows()}
        selected = st.selectbox('Registro', list(options), key=f'del_{table}')
        checked = st.checkbox('Confirmo a exclusão deste registro', key=f'check_{table}')
        if st.button('Excluir definitivamente', disabled=not checked, key=f'confirm_{table}'):
            execute(lambda:db_delete(table,options[selected]), 'Registro excluído.')


def money_chart(df, label, val, title, height=320):
    if df.empty or val not in df: st.info('Cadastre dados para visualizar este gráfico.'); return
    groups = df.groupby(label, as_index=False)[val].sum().sort_values(val,ascending=False)
    fig = px.pie(groups, names=label, values=val, hole=.67, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition='outside', textinfo='percent+label')
    fig.update_layout(title=title, showlegend=False)
    st.plotly_chart(chart_style(fig, height), use_container_width=True)


def gather():
    tables = {}
    for key in ALLOWED:
        tables[key] = db_read(key)
    return tables


def main():
    configured_password = str(secret('APP_PASSWORD'))
    if configured_password:
        if not st.session_state.get('access_granted', False):
            st.markdown('<div class="hero"><div class="kicker">Área protegida</div><h2>◈ Patrimônio 360</h2><p>Informe a senha de acesso configurada no servidor.</p></div>', unsafe_allow_html=True)
            with st.form('login'):
                password = st.text_input('Senha', type='password')
                if st.form_submit_button('Entrar', type='primary'):
                    import hmac
                    if hmac.compare_digest(password, configured_password):
                        st.session_state.access_granted = True
                        st.rerun()
                    else:
                        st.error('Senha incorreta.')
            st.stop()
    with st.sidebar:
        st.markdown('<div class="brand">◈ PATRIMÔNIO 360<small>FINANÇAS • CONTROLE • FUTURO</small></div>', unsafe_allow_html=True)
        st.divider()
        menu = st.radio('Navegação', [
            'Visão geral', 'Meu patrimônio', 'Dívidas e passivos', 'Investimentos',
            'Fluxo de caixa', 'Contas e orçamento', 'Metas financeiras',
            'Simulador', 'Relatórios e dados'
        ], label_visibility='collapsed', key='nav')
        st.divider()
        st.caption('Dados locais (SQLite)' if get_store()[0]=='sqlite' else 'Dados em nuvem (Supabase)')
        st.caption('Valores em reais (BRL) • Uso pessoal')
        if configured_password and st.button('Sair', use_container_width=True):
            st.session_state.access_granted = False
            st.rerun()
    try:
        d = gather()
    except Exception as error:
        st.error(f'Falha ao carregar dados: {error}. Verifique tabelas, permissões e configuração do banco.')
        st.stop()

    ativos, passivos, carteira = d['ativos'], d['passivos'], d['carteira_invest']
    patrimonio_bruto = total(ativos,'valor') + total(carteira,'valor_atual')
    dividas = total(passivos,'valor_total')
    liquido = patrimonio_bruto - dividas
    renda = total(d['fontes_renda'],'valor')
    despesas = total(d['despesas_variaveis'],'valor')
    despesas_fixas = total(d['gastos_fixos'],'valor')
    today = date.today()
    mes, ano = today.month, today.year
    rendas_mes = d['fontes_renda']
    if not rendas_mes.empty:
        rendas_mes = rendas_mes[(pd.to_numeric(rendas_mes['mes'],errors='coerce')==mes)&(pd.to_numeric(rendas_mes['ano'],errors='coerce')==ano)]
    despesas_mes = d['despesas_variaveis']
    if not despesas_mes.empty:
        parsed = pd.to_datetime(despesas_mes['data'],errors='coerce')
        despesas_mes = despesas_mes[(parsed.dt.month==mes)&(parsed.dt.year==ano)]
    receita_mes, gasto_mes = total(rendas_mes,'valor'), total(despesas_mes,'valor')
    saldo_mes = receita_mes - gasto_mes - despesas_fixas

    st.markdown(f'<div class="hero"><div class="kicker">CENTRAL PATRIMONIAL • {escape(menu.upper())}</div><h2>Seu dinheiro, com visão completa.</h2><p>Patrimônio, investimentos, dívidas e fluxo de caixa organizados em um único lugar.</p></div>', unsafe_allow_html=True)

    if menu=='Visão geral':
        st.subheader('Resumo do seu patrimônio')
        a,b,c,e = st.columns(4)
        a.metric('Patrimônio líquido',brl(liquido))
        b.metric('Bens e investimentos',brl(patrimonio_bruto))
        c.metric('Total de dívidas',brl(dividas))
        e.metric('Saldo estimado do mês',brl(saldo_mes))
        st.caption('Patrimônio líquido = ativos cadastrados + investimentos − dívidas. Saldo do mês = rendas lançadas − despesas do mês − gastos fixos cadastrados.')
        x,y=st.columns([1.2,1])
        with x:
            st.markdown('### Composição patrimonial')
            vals = [total(ativos,'valor'),total(carteira,'valor_atual')]
            if sum(vals)>0:
                fig=px.pie(names=['Bens e outros ativos','Investimentos'],values=vals,hole=.67,color_discrete_sequence=[C['blue'],C['teal']])
                fig.update_traces(textinfo='label+percent')
                st.plotly_chart(chart_style(fig),use_container_width=True)
            else:st.info('Adicione ativos ou investimentos para visualizar a composição.')
        with y:
            st.markdown('### Indicadores essenciais')
            for name,value in [('Receita do mês',receita_mes),('Gastos variáveis do mês',gasto_mes),('Gastos fixos cadastrados',despesas_fixas),('Investimentos atuais',total(carteira,'valor_atual'))]:
                st.metric(name,brl(value))
        st.markdown('### Próximas contas')
        contas=d['contas_pagar']
        if not contas.empty:
            contas = contas[~contas['pago'].astype(str).str.lower().isin(['true','1'])]
            contas=contas.sort_values('vencimento').head(6)
        show_table(contas,['descricao','valor','vencimento','categoria'],height=280)
        st.info('Os valores são os que você cadastrou; não são atualizados automaticamente por corretoras ou bancos.')

    elif menu=='Meu patrimônio':
        st.subheader('Bens e ativos')
        st.caption('Cadastre imóveis, veículos, reservas e outros bens. Investimentos financeiros são registrados separadamente para evitar soma em duplicidade.')
        x,y,z=st.columns(3)
        x.metric('Valor dos ativos',brl(total(ativos,'valor')))
        y.metric('Quantidade de ativos',len(ativos))
        z.metric('Patrimônio líquido total',brl(liquido))
        tab1,tab2=st.tabs(['Inventário de ativos','Análise por categoria'])
        with tab1:
            with st.form('new_ativo',clear_on_submit=True):
                a,b,c=st.columns([2,1.3,1.2])
                nome=a.text_input('Nome do bem',placeholder='Ex.: Apartamento')
                categoria=b.selectbox('Categoria',ATIVO_TIPOS)
                valor=c.number_input('Valor atual (R$)',min_value=0.0,step=100.0)
                if st.form_submit_button('Adicionar ativo',type='primary'):
                    if nome.strip():execute(lambda:db_insert('ativos',{'nome':nome.strip(),'categoria':categoria,'valor':valor}))
                    else:st.warning('Preencha o nome.')
            show_table(ativos,['nome','categoria','valor'])
            remove_record('ativos',ativos,'nome')
        with tab2:money_chart(ativos,'categoria','valor','Ativos por categoria')

    elif menu=='Dívidas e passivos':
        st.subheader('Gestão de dívidas')
        x,y=st.columns(2)
        x.metric('Saldo total de dívidas',brl(dividas))
        y.metric('Dívidas cadastradas',len(passivos))
        with st.form('new_divida',clear_on_submit=True):
            a,b,c=st.columns(3)
            nome=a.text_input('Nome da dívida',placeholder='Ex.: Financiamento')
            tipo=b.selectbox('Tipo',['Financiamento','Empréstimo','Cartão','Parcelamento','Outros'])
            saldo=c.number_input('Saldo devedor (R$)',min_value=0.0,step=100.0)
            a,b=st.columns(2)
            parcelas=a.number_input('Parcelas restantes',min_value=0,step=1)
            juros=b.number_input('Juros mensais (%)',min_value=0.0,step=0.1)
            if st.form_submit_button('Registrar dívida',type='primary'):
                if nome.strip():execute(lambda:db_insert('passivos',{'nome':nome.strip(),'tipo':tipo,'valor_total':saldo,'parcelas_restantes':parcelas,'juros_mensal':juros}))
                else:st.warning('Preencha o nome.')
        show_table(passivos,['nome','tipo','valor_total','parcelas_restantes','juros_mensal'])
        if not passivos.empty:
            st.markdown('### Ordem sugerida por juros')
            st.caption('Critério: maior taxa de juros mensal primeiro. Não substitui análise de contratos e outras condições.')
            show_table(passivos.sort_values('juros_mensal',ascending=False),['nome','valor_total','juros_mensal'],height=260)
        remove_record('passivos',passivos,'nome')

    elif menu=='Investimentos':
        st.subheader('Carteira de investimentos')
        investido=total(carteira,'valor_investido')
        atual=total(carteira,'valor_atual')
        ganho=atual-investido
        a,b,c=st.columns(3)
        a.metric('Total aplicado',brl(investido))
        b.metric('Valor atual',brl(atual))
        c.metric('Variação acumulada',brl(ganho),delta=pct(100*ganho/investido) if investido else None)
        with st.form('new_investimento',clear_on_submit=True):
            a,b=st.columns(2)
            nome=a.text_input('Ativo / investimento',placeholder='Ex.: CDB liquidez diária')
            classe=b.selectbox('Classe',INV_CLASSES)
            a,b,c=st.columns(3)
            aplicado=a.number_input('Valor investido',min_value=0.0,step=100.0)
            valor=b.number_input('Valor atual',min_value=0.0,step=100.0)
            dia=c.date_input('Data do aporte',value=today)
            if st.form_submit_button('Adicionar investimento',type='primary'):
                if nome.strip():execute(lambda:db_insert('carteira_invest',{'ativo':nome.strip(),'classe':classe,'valor_investido':aplicado,'valor_atual':valor,'data_aporte':dia.isoformat()}))
                else:st.warning('Preencha o ativo.')
        left,right=st.columns([1.2,1])
        with left:
            show_table(carteira,['ativo','classe','valor_investido','valor_atual','data_aporte'])
            remove_record('carteira_invest',carteira,'ativo')
        with right:money_chart(carteira,'classe','valor_atual','Alocação atual por classe')
        if not carteira.empty:
            with st.expander('Atualizar valor de mercado de um investimento'):
                opts={f"#{int(r['id'])} · {r['ativo']}":r for _,r in carteira.iterrows()}
                item=opts[st.selectbox('Selecione',list(opts))]
                novo=st.number_input('Novo valor atual (R$)',min_value=0.0,value=float(item['valor_atual']),step=100.0)
                if st.button('Salvar nova avaliação',type='primary'):
                    execute(lambda:db_update('carteira_invest',item['id'],{'valor_atual':novo}))

    elif menu=='Fluxo de caixa':
        st.subheader('Entradas e saídas')
        f1,f2=st.columns(2)
        with f1:
            st.markdown('### Registrar receita')
            with st.form('new_receita',clear_on_submit=True):
                desc=st.text_input('Descrição da receita',placeholder='Salário, aluguel recebido...')
                valor=st.number_input('Valor recebido (R$)',min_value=0.01,step=100.0)
                a,b=st.columns(2)
                m=a.selectbox('Mês',list(range(1,13)),index=mes-1)
                yr=b.number_input('Ano',min_value=2000,max_value=2100,value=ano)
                tipo=st.selectbox('Tipo de receita',['Salário','Extra','Aluguel','Rendimento','Outros'])
                if st.form_submit_button('Salvar receita',type='primary'):
                    if desc.strip():execute(lambda:db_insert('fontes_renda',{'descricao':desc.strip(),'valor':valor,'mes':m,'ano':int(yr),'tipo':tipo}))
                    else:st.warning('Informe a descrição.')
        with f2:
            st.markdown('### Registrar despesa')
            with st.form('new_despesa',clear_on_submit=True):
                desc=st.text_input('Descrição da despesa',placeholder='Supermercado, combustível...')
                valor=st.number_input('Valor pago (R$)',min_value=0.01,step=50.0)
                dt=st.date_input('Data',value=today)
                categoria=st.selectbox('Categoria',CATEGORIAS)
                if st.form_submit_button('Salvar despesa',type='primary'):
                    if desc.strip():execute(lambda:db_insert('despesas_variaveis',{'descricao':desc.strip(),'valor':valor,'data':dt.isoformat(),'categoria':categoria}))
                    else:st.warning('Informe a descrição.')
        st.divider()
        st.markdown('### Resumo por mês')
        last_months=[]
        for offset in range(11,-1,-1):
            year = ano + (mes - 1 - offset)//12
            month = (mes - 1 - offset)%12 + 1
            r=d['fontes_renda']; e=d['despesas_variaveis']
            if not r.empty:
                r=r[(pd.to_numeric(r['mes'],errors='coerce')==month)&(pd.to_numeric(r['ano'],errors='coerce')==year)]
            if not e.empty:
                dates=pd.to_datetime(e['data'],errors='coerce')
                e=e[(dates.dt.month==month)&(dates.dt.year==year)]
            last_months.append({'Mês':f'{month:02}/{year}','Receitas':total(r,'valor'),'Despesas':total(e,'valor')})
        hist=pd.DataFrame(last_months)
        fig=go.Figure()
        fig.add_bar(x=hist['Mês'],y=hist['Receitas'],name='Receitas',marker_color=C['teal'])
        fig.add_bar(x=hist['Mês'],y=hist['Despesas'],name='Despesas variáveis',marker_color=C['red'])
        fig.update_layout(barmode='group')
        st.plotly_chart(chart_style(fig,380),use_container_width=True)
        x,y=st.columns(2)
        with x:
            st.markdown('#### Histórico de receitas')
            show_table(d['fontes_renda'],['descricao','tipo','valor','mes','ano'])
            remove_record('fontes_renda',d['fontes_renda'],'descricao')
        with y:
            st.markdown('#### Histórico de despesas')
            show_table(d['despesas_variaveis'],['data','descricao','categoria','valor'])
            remove_record('despesas_variaveis',d['despesas_variaveis'],'descricao')

    elif menu=='Contas e orçamento':
        st.subheader('Custos fixos e vencimentos')
        x,y,z=st.columns(3)
        x.metric('Gastos fixos mensais',brl(despesas_fixas))
        vencidas=d['contas_pagar']
        if not vencidas.empty:
            vencidas=vencidas[(~vencidas['pago'].astype(str).str.lower().isin(['true','1'])) & (pd.to_datetime(vencidas['vencimento'],errors='coerce').dt.date<today)]
        y.metric('Contas vencidas',len(vencidas))
        z.metric('Despesas variáveis neste mês',brl(gasto_mes))
        x,y=st.columns(2)
        with x:
            st.markdown('### Despesa fixa')
            with st.form('new_fixo',clear_on_submit=True):
                desc=st.text_input('Descrição',placeholder='Internet, condomínio...')
                valor=st.number_input('Valor mensal (R$)',min_value=0.01,step=10.0)
                if st.form_submit_button('Adicionar custo fixo',type='primary'):
                    if desc.strip():execute(lambda:db_insert('gastos_fixos',{'descricao':desc.strip(),'valor':valor}))
                    else:st.warning('Informe a descrição.')
            show_table(d['gastos_fixos'],['descricao','valor'])
            remove_record('gastos_fixos',d['gastos_fixos'],'descricao')
        with y:
            st.markdown('### Conta a pagar')
            with st.form('new_conta',clear_on_submit=True):
                desc=st.text_input('Descrição da conta')
                valor=st.number_input('Valor da conta (R$)',min_value=0.01,step=10.0)
                dia=st.date_input('Vencimento',value=today)
                categoria=st.selectbox('Categoria',CATEGORIAS)
                if st.form_submit_button('Adicionar conta',type='primary'):
                    if desc.strip():execute(lambda:db_insert('contas_pagar',{'descricao':desc.strip(),'valor':valor,'vencimento':dia.isoformat(),'categoria':categoria,'pago':False}))
                    else:st.warning('Informe a descrição.')
            show_table(d['contas_pagar'],['descricao','valor','vencimento','pago','categoria'])
            if not d['contas_pagar'].empty:
                with st.expander('Marcar conta como paga / pendente'):
                    opts={f"#{int(r['id'])} · {r['descricao']}":r for _,r in d['contas_pagar'].iterrows()}
                    row=opts[st.selectbox('Conta',list(opts))]
                    pago=st.checkbox('Conta paga',value=str(row['pago']).lower() in ('1','true'))
                    if st.button('Atualizar situação'):
                        execute(lambda:db_update('contas_pagar',row['id'],{'pago':pago}))
            remove_record('contas_pagar',d['contas_pagar'],'descricao')
        st.caption('Acompanhe despesas fixas e contas a pagar separadamente. Se uma conta também for uma despesa fixa, evite somá-la duas vezes ao fazer análises manuais.')

    elif menu=='Metas financeiras':
        st.subheader('Objetivos patrimoniais')
        metas=d['metas_financeiras']
        with st.form('new_meta',clear_on_submit=True):
            nome=st.text_input('Nome da meta',placeholder='Reserva de emergência, imóvel...')
            a,b,c=st.columns(3)
            alvo=a.number_input('Valor objetivo (R$)',min_value=0.01,step=500.0)
            atual=b.number_input('Já acumulado (R$)',min_value=0.0,step=100.0)
            prazo=c.number_input('Prazo (anos)',min_value=1,max_value=80,value=3)
            categoria=st.selectbox('Categoria',['Reserva','Imóvel','Aposentadoria','Viagem','Educação','Outros'])
            if st.form_submit_button('Criar meta',type='primary'):
                if nome.strip():execute(lambda:db_insert('metas_financeiras',{'nome':nome.strip(),'valor_alvo':alvo,'valor_atual':atual,'prazo_anos':int(prazo),'categoria':categoria}))
                else:st.warning('Informe o nome da meta.')
        if metas.empty:st.info('Crie uma meta para acompanhar seu progresso.')
        else:
            for _,r in metas.iterrows():
                progresso=min(1.0,max(0.0,float(r['valor_atual'])/max(float(r['valor_alvo']),.01)))
                st.markdown(f"**{escape(str(r['nome']))}** · {brl(r['valor_atual'])} de {brl(r['valor_alvo'])} · {pct(progresso*100)}")
                st.progress(progresso)
            with st.expander('Atualizar o acumulado de uma meta'):
                opts={f"#{int(r['id'])} · {r['nome']}":r for _,r in metas.iterrows()}
                row=opts[st.selectbox('Meta',list(opts))]
                v=st.number_input('Valor já acumulado',value=float(row['valor_atual']),min_value=0.0,step=100.0)
                if st.button('Atualizar meta',type='primary'):execute(lambda:db_update('metas_financeiras',row['id'],{'valor_atual':v}))
            remove_record('metas_financeiras',metas,'nome')

    elif menu=='Simulador':
        st.subheader('Simulador de independência financeira')
        st.caption('Projeções hipotéticas com capitalização mensal, sem impostos, inflação ou taxas. Rentabilidade futura não é garantida.')
        a,b=st.columns(2)
        inicial=a.number_input('Capital inicial (R$)',min_value=0.0,value=float(total(carteira,'valor_atual')),step=100.0)
        mensal=b.number_input('Aporte mensal (R$)',min_value=0.0,value=500.0,step=100.0)
        a,b=st.columns(2)
        prazo=a.slider('Prazo em anos',1,40,15)
        taxa=b.slider('Rentabilidade anual estimada (%)',0.0,20.0,8.0,0.5)
        rm=(1+taxa/100)**(1/12)-1
        saldo=inicial
        points=[{'Ano':0,'Projetado':inicial,'Aplicado':inicial}]
        for i in range(1,prazo*12+1):
            saldo=saldo*(1+rm)+mensal
            if i%12==0:
                points.append({'Ano':i//12,'Projetado':saldo,'Aplicado':inicial+mensal*i})
        aporte=inicial+mensal*prazo*12
        x,y,z=st.columns(3)
        x.metric('Montante projetado',brl(saldo))
        y.metric('Total aportado',brl(aporte))
        z.metric('Rendimento projetado',brl(saldo-aporte))
        data=pd.DataFrame(points)
        fig=go.Figure()
        fig.add_scatter(x=data['Ano'],y=data['Projetado'],mode='lines',name='Patrimônio projetado',line=dict(color=C['teal'],width=3))
        fig.add_scatter(x=data['Ano'],y=data['Aplicado'],mode='lines',name='Total aportado',line=dict(color=C['blue'],width=2,dash='dash'))
        fig.update_layout(xaxis_title='Anos',yaxis_title='R$')
        st.plotly_chart(chart_style(fig,400),use_container_width=True)
        st.download_button('Exportar projeção CSV',data.to_csv(index=False).encode('utf-8-sig'),file_name='projecao_patrimonial.csv',mime='text/csv')

    elif menu=='Relatórios e dados':
        st.subheader('Relatórios e exportação')
        st.caption('Exporte relatórios e faça cópias dos seus dados. Esta área não exclui nem modifica registros.')
        summary=pd.DataFrame([
            {'Indicador':'Patrimônio líquido','Valor':liquido},
            {'Indicador':'Ativos e bens','Valor':total(ativos,'valor')},
            {'Indicador':'Investimentos','Valor':total(carteira,'valor_atual')},
            {'Indicador':'Dívidas','Valor':dividas},
            {'Indicador':'Receitas do mês','Valor':receita_mes},
            {'Indicador':'Despesas variáveis do mês','Valor':gasto_mes},
            {'Indicador':'Despesas fixas cadastradas','Valor':despesas_fixas},
        ])
        show_table(summary,['Indicador','Valor'])
        st.download_button('Baixar resumo CSV',summary.to_csv(index=False).encode('utf-8-sig'),file_name='resumo_patrimonio.csv',mime='text/csv')
        try:
            mem=io.BytesIO()
            doc=SimpleDocTemplate(mem,pagesize=A4)
            styles=getSampleStyleSheet()
            story=[Paragraph('Patrimônio 360 — Resumo Financeiro',styles['Title']),Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M'),styles['Normal']),Spacer(1,20)]
            rows=[['Indicador','Valor']]+[[str(r['Indicador']),brl(r['Valor'])] for _,r in summary.iterrows()]
            tab=Table(rows,colWidths=[280,160])
            tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#163A58')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#C4D2E0')),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10)]))
            story.append(tab)
            doc.build(story)
            st.download_button('Baixar relatório em PDF',mem.getvalue(),file_name='relatorio_patrimonial.pdf',mime='application/pdf',type='primary')
        except Exception as ex:st.error(f'Erro ao gerar PDF: {ex}')
        st.markdown('### Backup de tabelas')
        st.caption('Baixe um arquivo CSV por tabela. No SQLite local, também preserve o arquivo patrimonio360.db como backup completo.')
        for table in sorted(ALLOWED):
            st.download_button(f'CSV · {table}',d[table].to_csv(index=False).encode('utf-8-sig'),file_name=f'{table}.csv',mime='text/csv',key=f'export_{table}')
        st.markdown('### Integridade dos registros')
        st.info('O app não escreve ou apaga dados automaticamente ao abrir páginas. Inclusões, atualizações e exclusões exigem ações explícitas.')


if __name__=='__main__':
    main()
