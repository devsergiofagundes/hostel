import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro | Elite Suite", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="expanded"
)

# --- INJEÇÃO DE CSS DE ALTO NÍVEL ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #F4F7FE;
    }

    /* Ajuste de Texto nas Métricas (CORREÇÃO DO ERRO DE VISIBILIDADE) */
    [data-testid="stMetricValue"] {
        color: #1B254B !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #A3AED0 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }
    
    /* Card de Métrica Estilizado */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 20px;
        padding: 20px !important;
        box-shadow: 0px 45px 80px rgba(0, 0, 0, 0.02);
        border: 1px solid #E9EDF7;
    }

    /* Estilização da Sidebar */
    [data-testid="stSidebar"] {
        background-color: #111C44;
        border-right: 1px solid #1B254B;
    }
    [data-testid="stSidebar"] section[data-testid="stSidebarNav"] {
        background-color: transparent;
    }
    
    /* Botões Premium */
    .stButton>button {
        border-radius: 12px;
        background: #4318FF;
        color: white;
        border: none;
        padding: 0.6rem 1rem;
        font-weight: 700;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: #3311CC;
        box-shadow: 0px 4px 20px rgba(67, 24, 255, 0.4);
    }

    /* Esconder elementos desnecessários */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO E CONEXÃO ---
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
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Anterior", key="p"):
                st.session_state.data_filtro -= pd.DateOffset(months=1)
                st.rerun()
        with c2:
            st.markdown(f"<h3 style='text-align: center; color: #1B254B; margin:0;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h3>", unsafe_allow_html=True)
        with c3:
            if st.button("Próximo ➡️", key="n"):
                st.session_state.data_filtro += pd.DateOffset(months=1)
                st.rerun()
    st.write("")

# --- SIDEBAR PROFISSIONAL ---
with st.sidebar:
    st.markdown("<h1 style='color: white; font-size: 22px; text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #707EAE; text-align: center; font-size: 12px;'>SISTEMA DE GESTÃO ELITE</p>", unsafe_allow_html=True)
    st.divider()
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ELITE ---
if menu == "💰 Dashboard":
    st.markdown("<h2 style='color: #1B254B;'>Visão Geral Financeira</h2>", unsafe_allow_html=True)
    seletor_periodo()
    
    df_r = get_data_safe(ws_reservas)
    df_d = get_data_safe(ws_despesas)
    
    rec = 0
    if not df_r.empty and 'entrada' in df_r.columns:
        df_r['entrada'] = pd.to_datetime(df_r['entrada'])
        rec = df_r[(df_r['entrada'].dt.month == m) & (df_r['entrada'].dt.year == a)]['total'].sum()
    
    gas = 0
    if not df_d.empty and 'data' in df_d.columns:
        df_d['data'] = pd.to_datetime(df_d['data'])
        gas = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]['valor'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("FATURAMENTO BRUTO", f"R$ {rec:,.2f}")
    col2.metric("CUSTOS OPERACIONAIS", f"R$ {gas:,.2f}")
    col3.metric("LUCRO LÍQUIDO", f"R$ {rec-gas:,.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    c_graf1, c_graf2 = st.columns([2, 1])
    with c_graf1:
        st.markdown("<div style='background: white; padding: 20px; border-radius: 20px; border: 1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Performance Mensal")
        st.bar_chart({"Receita": rec, "Despesa": gas})
        st.markdown("</div>", unsafe_allow_html=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.markdown("<h2 style='color: #1B254B;'>Mapa de Reservas</h2>", unsafe_allow_html=True)
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = []
        for _, r in df.iterrows():
            events.append({
                "title": f"{r['quarto'].upper()} | {r['nome']}",
                "start": str(r['entrada']), "end": str(r['saida']),
                "backgroundColor": "#4318FF", "borderColor": "#4318FF"
            })
        calendar(events=events, options={"locale":"pt-br", "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek"}})

# --- RESERVAS ---
elif menu == "📋 Reservas":
    st.markdown("<h2 style='color: #1B254B;'>Controle de Hóspedes</h2>", unsafe_allow_html=True)
    seletor_periodo()
    
    with st.expander("✨ ADICIONAR NOVA RESERVA"):
        with st.form("f_res"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome do Hóspede")
            quarto = c2.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            ent = c1.date_input("Check-in")
            sai = c2.date_input("Check-out")
            val = st.number_input("Valor total da estadia", 0.0)
            if st.form_submit_button("Confirmar Reserva"):
                ws_reservas.append_row([int(datetime.now().timestamp()), nome, 1, quarto, str(ent), str(sai), (sai-ent).days, val])
                st.rerun()

    df = get_data_safe(ws_reservas)
    if not df.empty:
        df['entrada'] = pd.to_datetime(df['entrada'])
        df_f = df[(df['entrada'].dt.month == m) & (df['entrada'].dt.year == a)]
        st.dataframe(df_f, use_container_width=True, hide_index=True)

# --- DESPESAS ---
elif menu == "💸 Despesas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão de Gastos</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ REGISTRAR DESPESA"):
        with st.form("f_desp"):
            d_data = st.date_input("Data do Gasto")
            d_desc = st.text_input("Descrição do Item/Serviço")
            d_val = st.number_input("Valor do Gasto", 0.0)
            if st.form_submit_button("Registrar na Planilha"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d_data), d_desc, d_val])
                st.rerun()
    
    df_d = get_data_safe(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        df_f = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        st.dataframe(df_f, use_container_width=True, hide_index=True)
