import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro | Management Suite", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="auto"
)

# --- CSS DE ALTO NÍVEL (CORRIGIDO PARA MOBILE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #F4F7FE;
    }

    /* Correção do Botão de Menu Mobile */
    button[kind="headerNoContext"] {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 8px !important;
    }

    /* Ajuste de Texto nas Métricas */
    [data-testid="stMetricValue"] {
        color: #1B254B !important;
        font-size: 22px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #707EAE !important;
        font-size: 13px !important;
        font-weight: 600 !important;
    }
    
    /* Card de Métrica Estilizado */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 16px;
        padding: 15px !important;
        box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03);
        border: 1px solid #E9EDF7;
    }

    /* Sidebar Dark Pro */
    [data-testid="stSidebar"] {
        background-color: #111C44;
    }
    [data-testid="stSidebar"] * {
        color: #A3AED0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
        color: white !important;
    }
    
    /* Botões Premium */
    .stButton>button {
        border-radius: 10px;
        background: #4318FF;
        color: white;
        border: none;
        font-weight: 700;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÃO E DADOS ---
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

# --- COMPONENTES UI ---
def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("⬅️"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with c2:
        st.markdown(f"<h4 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("➡️"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 10px; letter-spacing: 2px;'>MANAGEMENT SUITE</p>", unsafe_allow_html=True)
    st.write("---")
    menu = st.selectbox("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ELITE ---
if menu == "💰 Dashboard":
    st.markdown("<h2 style='color: #1B254B;'>Análise de Performance</h2>", unsafe_allow_html=True)
    seletor_periodo()
    
    df_r = get_data_safe(ws_reservas)
    df_d = get_data_safe(ws_despesas)
    
    # Processamento Financeiro
    rec, gas = 0, 0
    if not df_r.empty and 'entrada' in df_r.columns:
        df_r['entrada'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['entrada'].dt.month == m) & (df_r['entrada'].dt.year == a)]
        rec = df_mes_r['total'].sum()
    
    if not df_d.empty and 'data' in df_d.columns:
        df_d['data'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        gas = df_mes_d['valor'].sum()

    # Métricas Principais
    c1, c2, c3 = st.columns(3)
    c1.metric("RECEITA TOTAL", f"R$ {rec:,.2f}")
    c2.metric("DESPESAS TOTAL", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    c3.metric("LUCRO LÍQUIDO", f"R$ {rec-gas:,.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Painel de Ocupação Real-Time (Gráficos)
    col_g1, col_g2 = st.columns([1, 1])
    
    with col_g1:
        st.markdown("<div style='background: white; padding: 20px; border-radius: 16px; border: 1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Receita por Quarto")
        if rec > 0:
            pie_data = df_mes_r.groupby('quarto')['total'].sum()
            st.bar_chart(pie_data) # Bar chart é mais limpo no mobile que o pie padrão
        else:
            st.info("Sem dados para o gráfico.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_g2:
        st.markdown("<div style='background: white; padding: 20px; border-radius: 16px; border: 1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Fluxo de Caixa")
        st.area_chart(pd.DataFrame({"Receita": [0, rec], "Despesa": [0, gas]}))
        st.markdown("</div>", unsafe_allow_html=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.markdown("<h2 style='color: #1B254B;'>Mapa de Ocupação</h2>", unsafe_allow_html=True)
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = []
        for _, r in df.iterrows():
            events.append({
                "title": f"{r['quarto']} - {r['nome']}",
                "start": str(r['entrada']), "end": str(r['saida']),
                "backgroundColor": "#4318FF", "borderColor": "#4318FF"
            })
        calendar(events=events, options={"locale":"pt-br", "initialView": "dayGridMonth"})

# --- MANTENDO RESERVAS E DESPESAS COM O MESMO PADRÃO ---
else:
    st.info("Utilize o menu lateral para gerir dados específicos.")
