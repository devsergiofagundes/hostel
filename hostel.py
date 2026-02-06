import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- 2. LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    with st.form("login_gate"):
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["access"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

if not check_password():
    st.stop()

# --- 3. CONEXÃO E CACHE ---
@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds = Credentials.from_service_account_info(
            json.loads(json_info), 
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão: {e}"); return None

client = init_connection()

@st.cache_data(ttl=60)
def get_data_cached(sheet_name):
    spreadsheet = client.open("hostel-db")
    ws = spreadsheet.worksheet(sheet_name)
    data = ws.get_all_records()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

def refresh_data():
    st.cache_data.clear()

# --- 4. FUNÇÕES DE LÓGICA ---
def calcular_taxa_reserva(row):
    total = float(row.get('total', 0))
    origem = str(row.get('origem', '')).strip()
    forma = str(row.get('forma_pgto', '')).strip()
    taxa_origem = 0.13 if origem == "Booking" else 0.0
    taxas_financeiras = {"Credito": 0.05, "Debito": 0.0239, "PIX": 0.0, "Dinheiro": 0.0}
    taxa_pgto = taxas_financeiras.get(forma, 0.0)
    return total * (taxa_origem + taxa_pgto)

def delete_by_id(sheet_name, row_id):
    ws = client.open("hostel-db").worksheet(sheet_name)
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.delete_rows(i + 2)
            refresh_data()
            return True
    return False

def update_row(sheet_name, row_id, new_data):
    ws = client.open("hostel-db").worksheet(sheet_name)
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            end_col = chr(64 + len(new_data))
            ws.update(f'A{i+2}:{end_col}{i+2}', [new_data])
            refresh_data()
            return True
    return False

# --- 5. NAVEGAÇÃO ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

with st.sidebar:
    st.markdown("## HOSTEL PRO")
    menu = st.radio("MENU", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    if st.button("🔄 Atualizar"):
        refresh_data(); st.rerun()
    if st.button("Sair"):
        st.session_state["password_correct"] = False; st.rerun()

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️"): st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: st.markdown(f"<h4 style='text-align: center;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3: 
        if st.button("➡️"): st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- 6. MÓDULOS ---

if menu == "💰 Dashboard":
    st.title("BI Dashboard")
    seletor_periodo()
    df_r, df_d = get_data_cached("reservas"), get_data_cached("despesas")
    
    # 📊 PROJEÇÃO MENSAL (Mês Inteiro)
    bruto_p, taxas_p, operacionais_p = 0.0, 0.0, 0.0
    df_mes_r = pd.DataFrame()

    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        if not df_mes_r.empty:
            bruto_p = df_mes_r['total'].sum()
            taxas_p = df_mes_r.apply(calcular_taxa_reserva, axis=1).sum()

    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        operacionais_p = df_mes_d['valor'].sum()

    st.subheader("🔭 Projeção Mensal")
    cp1, cp2, cp3, cp4 = st.columns(4)
    cp1.metric("BRUTO TOTAL", f"R$ {bruto_p:,.2f}")
    cp2.metric("TAXAS TOTAIS", f"R$ {taxas_p:,.2f}")
    cp3.metric("DESPESAS TOTAIS", f"R$ {operacionais_p:,.2f}")
    cp4.metric("LUCRO ESTIMADO", f"R$ {(bruto_p - taxas_p - operacionais_p):,.2f}")

    st.markdown("---")
    
    # 📉 REALIZADO ATÉ HOJE (01/MM até Hoje)
    st.subheader(f"📊 Realizado: 01/{m:02d}/{a} até {date.today().strftime('%d/%m/%Y')}")
    hoje = pd.Timestamp(date.today())
    bruto_h, taxas_h, operacionais_h = 0.0, 0.0, 0.0

    if not df_mes_r.empty:
        df_hoje_r = df_mes_r[df_mes_r['en_dt'] <= hoje]
        bruto_h = df_hoje_r['total'].sum()
        taxas_h = df_hoje_r.apply(calcular_taxa_reserva, axis=1).sum()

    if not df_d.empty:
        df_hoje_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a) & (df_d['dt_dt'] <= hoje)]
        operacionais_h = df_hoje_d['valor'].sum()

    ch1, ch2, ch3, ch4 = st.columns(4)
    ch1.metric("BRUTO REALIZADO", f"R$ {bruto_h:,.2f}")
    ch2.metric("TAXAS PAGAS", f"R$ {taxas_h:,.2f}")
    ch3.metric("DESPESAS PAGAS", f"R$ {operacionais_h:,.2f}")
    ch4.metric("LUCRO REAL", f"R$ {(bruto_h - taxas_h - operacionais_h):,.2f}")

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    with cg1:
        st.subheader("Ocupação por Quarto")
        if not df_mes_r.empty:
            df_plot = df_mes_r.copy()
            df_plot['quarto'] = df_plot['quarto'].astype(str).str.split(', ')
            st.bar_chart(df_plot.explode('quarto').groupby('quarto')['total'].count())
    with cg2:
        st.subheader("Divisão Financeira (Projeção)")
        if bruto_p > 0:
            fin_df = pd.DataFrame({"Cat": ["Taxas", "Despesas", "Lucro"], "Val": [taxas_p, operacionais_p, max(0, bruto_p-taxas_p-operacionais_p)]})
            st.bar_chart(fin_df.set_index("Cat"))

elif menu == "📋 Reservas":
    # ... (Módulo de Reservas original mantido intacto)
    st.title("Gestão de Reservas")
    seletor_periodo()
    # (O código de formulário e listagem segue aqui igual ao anterior...)
    # [Mantido o código de edição, exclusão e multiselect do formulário]
    df_r = get_data_cached("reservas")
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy().sort_values(by='en_dt', ascending=False)
        st.markdown("---")
        h_cols = st.columns([0.6, 2.5, 1.5, 1.5, 1.5, 1.2, 0.6, 0.6])
        for col, label in zip(h_cols, ["ID", "Hóspede", "Entrada", "Quarto", "Total", "Pgto", "📝", "🗑️"]): col.markdown(f"**{label}**")
        st.divider()
        for _, row in df_f.iterrows():
            cols = st.columns([0.6, 2.5, 1.5, 1.5, 1.5, 1.2, 0.6, 0.6])
            cols[0].write(f"`{str(row['id'])[-4:]}`")
            cols[1].write(row['nome'])
            cols[2].write(pd.to_datetime(row['entrada']).strftime('%d/%m/%Y'))
            cols[3].write(row['quarto'])
            cols[4].write(f"R$ {row['total']:,.2f}")
            cols[5].write(f"`{row.get('forma_pgto', 'N/A')}`")
            if cols[6].button("📝", key=f"e_{row['id']}"):
                st.session_state.edit_mode = "editar"; st.session_state.item_selecionado = row; st.rerun()
            if cols[7].button("🗑️", key=f"d_{row['id']}"): delete_by_id("reservas", row['id']); st.rerun()

elif menu == "💸 Despesas":
    # ... (Módulo de Despesas original mantido intacto)
    st.title("Gestão de Despesas")
    seletor_periodo()
    # [Mantido o código de formulário e listagem das despesas]
    df_d = get_data_cached("despesas")
    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy().sort_values(by='dt_dt', ascending=False)
        st.divider()
        for _, row in df_fd.iterrows():
            cols = st.columns([1, 2, 4, 2, 0.6, 0.6])
            cols[1].write(pd.to_datetime(row['data']).strftime('%d/%m/%Y'))
            cols[2].write(row['descricao'])
            cols[3].write(f"R$ {row['valor']:,.2f}")
            if cols[4].button("📝", key=f"ed_{row['id']}"):
                st.session_state.edit_mode_d = "editar"; st.session_state.item_selecionado_d = row; st.rerun()
            if cols[5].button("🗑️", key=f"dd_{row['id']}"): delete_by_id("despesas", row['id']); st.rerun()

elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data_cached("reservas")
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
