import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro | Management", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="expanded"
)

# --- CSS PROFISSIONAL ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 15px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #edf2f7;
    }
    .stButton>button {
        border-radius: 8px;
        background: linear-gradient(135deg, #3D5AFE 0%, #2A3EB1 100%);
        color: white; font-weight: 600; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO GLOBAL ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

# --- CONEXÃO ---
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
    # Normaliza nomes de colunas: remove espaços, acentos e põe em minúsculo
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

# --- UI COMPONENTS ---
def seletor_mes_pro():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️", key="prev"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with col2:
        st.markdown(f"<h4 style='text-align: center;'>{st.session_state.data_filtro.strftime('%B / %Y').upper()}</h4>", unsafe_allow_html=True)
    with col3:
        if st.button("➡️", key="next"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()

@st.dialog("Detalhes")
def detalhes_reserva(event_info):
    st.markdown(f"## {event_info['title']}")
    st.divider()
    if "extendedProps" in event_info:
        p = event_info["extendedProps"]
        c1, c2 = st.columns(2)
        c1.metric("Hóspedes", p.get('hospedes'))
        c2.metric("Total", f"R$ {p.get('total', 0):,.2f}")
    if st.button("Fechar"): st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🏨 HOSTEL PRO")
    menu = st.radio("NAVEGAÇÃO", ["Dashboard", "Agenda", "Reservas", "Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("💰 Financeiro")
    seletor_mes_pro()
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

    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", f"R$ {rec:,.2f}")
    c2.metric("Despesas", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    c3.metric("Resultado", f"R$ {rec-gas:,.2f}")

# --- AGENDA ---
elif menu == "Agenda":
    st.title("📅 Agenda")
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = []
        for _, r in df.iterrows():
            events.append({
                "title": f"{r['quarto']} - {r['nome']}",
                "start": str(r['entrada']), "end": str(r['saida']),
                "extendedProps": {"hospedes": r.get('hospedes', 1), "total": r.get('total', 0)}
            })
        state = calendar(events=events, options={"locale":"pt-br"}, key='hostel_calendar')
        if state.get("eventClick"): detalhes_reserva(state["eventClick"]["event"])

# --- RESERVAS ---
elif menu == "Reservas":
    st.title("📋 Reservas")
    seletor_mes_pro()
    with st.expander("➕ NOVA RESERVA"):
        with st.form("f_res"):
            nome = st.text_input("Nome")
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            ent = st.date_input("Entrada")
            sai = st.date_input("Saída")
            val = st.number_input("Valor", 0.0)
            if st.form_submit_button("Salvar"):
                ws_reservas.append_row([int(datetime.now().timestamp()), nome, 1, quarto, str(ent), str(sai), (sai-ent).days, val])
                st.rerun()
    df = get_data_safe(ws_reservas)
    if not df.empty:
        df['entrada'] = pd.to_datetime(df['entrada'])
        st.dataframe(df[(df['entrada'].dt.month == m) & (df['entrada'].dt.year == a)], use_container_width=True, hide_index=True)

# --- DESPESAS (ONDE ESTAVA O ERRO) ---
elif menu == "Despesas":
    st.title("💸 Despesas")
    seletor_mes_pro()
    with st.expander("➕ LANÇAR GASTO"):
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
        df_f = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        
        # Seleção segura de colunas: usa apenas as que existem de fato
        colunas_disponiveis = [c for c in ['data', 'descricao', 'valor'] if c in df_f.columns]
        
        if not df_f.empty:
            st.dataframe(df_f[colunas_disponiveis], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma despesa para este período.")
