import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro | Elite Management", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="auto"
)

# --- CSS DE ALTO NÍVEL ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #F4F7FE; }
    button[kind="headerNoContext"] { background-color: #4318FF !important; color: white !important; }
    [data-testid="stMetricValue"] { color: #1B254B !important; font-size: 24px !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #707EAE !important; font-size: 14px !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    [data-testid="stSidebar"] * { color: #A3AED0 !important; }
    .stButton>button { border-radius: 10px; background: #4318FF; color: white; font-weight: 700; width: 100%; border: none; }
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
if client:
    spreadsheet = client.open("hostel-db")
    ws_reservas = spreadsheet.worksheet("reservas")
    ws_despesas = spreadsheet.worksheet("despesas")
else: st.stop()

def get_data_safe(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

# --- UI COMPONENTS ---
def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("⬅️"):
            st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2:
        st.markdown(f"<h4 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("➡️"):
            st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    st.write("---")
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ---
if menu == "💰 Dashboard":
    st.markdown("<h2 style='color: #1B254B;'>Business Intelligence</h2>", unsafe_allow_html=True)
    seletor_periodo()
    df_r = get_data_safe(ws_reservas)
    df_d = get_data_safe(ws_despesas)
    
    rec, gas = 0, 0
    if not df_r.empty:
        df_r['entrada'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['entrada'].dt.month == m) & (df_r['entrada'].dt.year == a)]
        rec = df_mes_r['total'].sum()
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        gas = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]['valor'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("RECEITA", f"R$ {rec:,.2f}")
    col2.metric("DESPESAS", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    col3.metric("LUCRO", f"R$ {rec-gas:,.2f}")

    c_g1, c_g2 = st.columns(2)
    with c_g1:
        if rec > 0:
            df_exp = df_mes_r.copy()
            df_exp['quarto'] = df_exp['quarto'].astype(str).str.split(', ')
            df_exp = df_exp.explode('quarto')
            st.bar_chart(df_exp.groupby('quarto')['total'].sum())
    with c_g2:
        st.area_chart(pd.DataFrame({"Receita": [0, rec], "Despesa": [0, gas]}))

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=events, options={"locale":"pt-br"})

# --- RESERVAS (CORRIGIDO: HOSPEDES MANUAL) ---
elif menu == "📋 Reservas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão de Hóspedes</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ NOVA RESERVA"):
        with st.form("f_res"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome do Hóspede")
            # CAMPO HOSPEDES RESTAURADO
            num_hospedes = c2.number_input("Quantidade de Hóspedes", min_value=1, value=1, step=1)
            
            quartos = c1.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=["Master"])
            ent = c2.date_input("Check-in")
            
            sai = c1.date_input("Check-out")
            val = c2.number_input("Valor Total", 0.0)
            
            if st.form_submit_button("Confirmar Reserva"):
                diarias = (sai - ent).days
                if diarias > 0 and nome and quartos:
                    ws_reservas.append_row([
                        int(datetime.now().timestamp()), 
                        nome, 
                        num_hospedes, # VALOR MANUAL SALVO AQUI
                        ", ".join(quartos), 
                        str(ent), 
                        str(sai), 
                        diarias, 
                        val
                    ])
                    st.success("Reserva salva com sucesso!")
                    st.rerun()
                else: st.error("Erro: Verifique o nome, quartos e se a saída é posterior à entrada.")
    
    df = get_data_safe(ws_reservas)
    if not df.empty:
        df['entrada'] = pd.to_datetime(df['entrada'])
        st.dataframe(df[(df['entrada'].dt.month == m) & (df['entrada'].dt.year == a)], use_container_width=True, hide_index=True)

# --- DESPESAS ---
elif menu == "💸 Despesas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão Financeira</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ NOVA DESPESA"):
        with st.form("f_desp"):
            d_data = st.date_input("Data")
            d_desc = st.text_input("Descrição")
            d_val = st.number_input("Valor", 0.0)
            if st.form_submit_button("Lançar"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d_data), d_desc, d_val])
                st.rerun()
    df_d = get_data_safe(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        st.dataframe(df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)], use_container_width=True, hide_index=True)
