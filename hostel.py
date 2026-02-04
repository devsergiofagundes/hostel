import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #F4F7FE; }
    
    .stButton>button {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        box-shadow: 0px 4px 12px rgba(67, 24, 255, 0.2) !important;
    }
    
    .btn-delete > div > button { background-color: #FF4B4B !important; }

    [data-testid="stMetricValue"] { color: #1B254B !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0,0,0,0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÃO ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds = Credentials.from_service_account_info(json.loads(json_info), 
                scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

client = init_connection()
spreadsheet = client.open("hostel-db")
ws_res = spreadsheet.worksheet("reservas")
ws_des = spreadsheet.worksheet("despesas")

def get_data(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

def delete_by_id(ws, row_id):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.delete_rows(i + 2)
            return True
    return False

def update_row(ws, row_id, new_data, cols="H"):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.update(f'A{i+2}:{cols}{i+2}', [new_data])
            return True
    return False

# --- NAVEGAÇÃO ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: white;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️ Anterior"): st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: st.markdown(f"<h4 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("Próximo ➡️"): st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- DASHBOARD (FIXED) ---
if menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    
    df_r = get_data(ws_res)
    df_d = get_data(ws_des)
    
    rec, gas = 0.0, 0.0
    df_mes_r = pd.DataFrame()
    df_mes_d = pd.DataFrame()

    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        rec = df_mes_r['total'].sum()

    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        gas = df_mes_d['valor'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("RECEITA NO PERÍODO", f"R$ {rec:,.2f}")
    c2.metric("DESPESAS NO PERÍODO", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    c3.metric("LUCRO LÍQUIDO", f"R$ {rec-gas:,.2f}")

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    
    with cg1:
        st.subheader("Ocupação por Quarto")
        if not df_mes_r.empty:
            # Lógica para separar quartos múltiplos (Master, Studio) e contar no gráfico
            df_plot = df_mes_r.copy()
            df_plot['quarto'] = df_plot['quarto'].astype(str).str.split(', ')
            df_exploded = df_plot.explode('quarto')
            # Gráfico de barras por quarto
            st.bar_chart(df_exploded.groupby('quarto')['total'].count())
        else: st.info("Sem dados para este mês.")

    with cg2:
        st.subheader("Balanço Simples")
        st.bar_chart(pd.DataFrame({"Valores": [rec, gas]}, index=["Receita", "Despesa"]))

# --- RESERVAS (MÊS ATUAL) ---
elif menu == "📋 Reservas":
    st.title("Gestão de Hóspedes")
    seletor_periodo()
    df_r = get_data(ws_res)
    df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
    df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()

    tab1, tab2 = st.tabs(["➕ Nova Reserva", "⚙️ Gerenciar"])
    with tab1:
        with st.form("f_new"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome")
            h = c2.number_input("Hóspedes", 1)
            q = c1.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=["Master"])
            en = c2.date_input("Check-in")
            sa = c1.date_input("Check-out")
            vl = c2.number_input("Total R$", 0.0)
            if st.form_submit_button("Confirmar"):
                ws_res.append_row([int(datetime.now().timestamp()), n, h, ", ".join(q), str(en), str(sa), (sa-en).days, vl])
                st.rerun()
    with tab2:
        if not df_f.empty:
            id_s = st.selectbox("ID para Editar/Apagar", df_f['id'].tolist())
            if st.button("🗑️ APAGAR RESERVA", key="delete_res"):
                delete_by_id(ws_res, id_s); st.rerun()
    
    st.dataframe(df_f.drop(columns=['en_dt']), use_container_width=True, hide_index=True)

# --- DESPESAS (MÊS ATUAL) ---
elif menu == "💸 Despesas":
    st.title("Gestão Financeira")
    seletor_periodo()
    df_d = get_data(ws_des)
    df_d['dt_dt'] = pd.to_datetime(df_d['data'])
    df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()

    tab1, tab2 = st.tabs(["➕ Lançar", "⚙️ Gerenciar"])
    with tab1:
        with st.form("f_des"):
            d = st.date_input("Data")
            ds = st.text_input("Descrição")
            v = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Lançar"):
                ws_des.append_row([int(datetime.now().timestamp()), str(d), ds, v])
                st.rerun()
    with tab2:
        if not df_fd.empty:
            id_d = st.selectbox("ID para Apagar", df_fd['id'].tolist())
            if st.button("🗑️ APAGAR DESPESA", key="delete_des"):
                delete_by_id(ws_des, id_d); st.rerun()

    st.dataframe(df_fd.drop(columns=['dt_dt']), use_container_width=True, hide_index=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs, options={"locale":"pt-br"})
