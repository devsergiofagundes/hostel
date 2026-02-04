import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA (ESTILO PREMIUM) ---
st.set_page_config(
    page_title="Hostel Pro | Management", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="expanded"
)

# --- INJEÇÃO DE CSS PROFISSIONAL ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
        background-color: #f8f9fa;
    }
    
    /* Estilização dos Cards de Métrica */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 15px 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #edf2f7;
    }
    
    /* Estilização de Botões */
    .stButton>button {
        border-radius: 8px;
        background: linear-gradient(135deg, #3D5AFE 0%, #2A3EB1 100%);
        color: white;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(61, 90, 254, 0.3);
        color: white;
    }

    /* Tabs e Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1A202C;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Formulários e Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO GLOBAL ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

# --- CONEXÃO SEGURA ---
@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds_dict = json.loads(json_info)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except: return None

client = init_connection()
if client:
    spreadsheet = client.open("hostel-db")
    ws_reservas = spreadsheet.worksheet("reservas")
    ws_despesas = spreadsheet.worksheet("despesas")
else: st.stop()

def get_data(ws): return pd.DataFrame(ws.get_all_records())

# --- UI COMPONENTS ---
def seletor_mes_pro():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️", key="prev"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with col2:
        texto = st.session_state.data_filtro.strftime("%B / %Y").upper()
        st.markdown(f"<h4 style='text-align: center; color: #2D3748;'>{texto}</h4>", unsafe_allow_html=True)
    with col3:
        if st.button("➡️", key="next"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()

@st.dialog("Detalhes da Reserva")
def detalhes_reserva(event_info):
    st.markdown(f"## {event_info['title']}")
    st.markdown(f"**Check-in:** `{event_info['start']}` | **Check-out:** `{event_info['end']}`")
    st.divider()
    if "extendedProps" in event_info:
        p = event_info["extendedProps"]
        c1, c2 = st.columns(2)
        c1.metric("👤 Hóspedes", p.get('hospedes'))
        c2.metric("💰 Total", f"R$ {p.get('total', 0):,.2f}")
    st.write(" ")
    if st.button("Fechar Janela", use_container_width=True): st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>HOSTEL PRO</h2>", unsafe_allow_html=True)
    st.divider()
    menu = st.radio("NAVEGAÇÃO", ["Dashboard", "Agenda", "Reservas", "Despesas"], label_visibility="collapsed")
    st.spacer = st.container()
    st.write(" ")
    st.caption("v2.5 Professional Cloud")

# --- LÓGICA DE MÓDULOS ---
m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

if menu == "Dashboard":
    st.title("💰 Visão Financeira")
    seletor_mes_pro()
    
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    
    rec = 0
    if not df_res.empty:
        df_res['entrada'] = pd.to_datetime(df_res['entrada'])
        rec = df_res[(df_res['entrada'].dt.month == m) & (df_res['entrada'].dt.year == a)]['total'].sum()
    
    gas = 0
    if not df_desp.empty:
        df_desp['data'] = pd.to_datetime(df_desp['data'])
        gas = df_desp[(df_desp['data'].dt.month == m) & (df_desp['data'].dt.year == a)]['valor'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Receitas", f"R$ {rec:,.2f}")
    col2.metric("Despesas", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    col3.metric("Lucro Líquido", f"R$ {rec-gas:,.2f}")
    
    st.divider()
    if rec > 0 or gas > 0:
        st.subheader("Ocupação vs Gastos")
        st.area_chart(pd.DataFrame({"Receita": [0, rec], "Despesa": [0, gas]}))

elif menu == "Agenda":
    st.title("📅 Mapa de Ocupação")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        events = []
        for _, r in df_res.iterrows():
            cor = "#3D5AFE" if r['quarto'] == "Master" else "#00C853" if r['quarto'] == "Studio" else "#FF6D00"
            events.append({
                "title": f"{r['quarto']} - {r['nome']}",
                "start": str(r['entrada']), "end": str(r['saida']), "color": cor,
                "extendedProps": {"hospedes": r['hospedes'], "total": r['total']}
            })
        state = calendar(events=events, options={"locale":"pt-br", "selectable": True}, key='hostel_calendar')
        if state.get("eventClick"):
            detalhes_reserva(state["eventClick"]["event"])

elif menu == "Reservas":
    st.title("📋 Gestão de Hóspedes")
    seletor_mes_pro()
    
    with st.expander("✨ CADASTRAR NOVA RESERVA"):
        with st.form("f_res", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome Completo")
            quarto = c2.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            ent = c1.date_input("Check-in")
            sai = c2.date_input("Check-out")
            val = st.number_input("Valor da Reserva (R$)", 0.0)
            if st.form_submit_button("Confirmar Reserva"):
                ws_reservas.append_row([int(datetime.now().timestamp()), nome, 1, quarto, str(ent), str(sai), (sai-ent).days, val])
                st.rerun()

    df_res = get_data(ws_reservas)
    if not df_res.empty:
        df_res['entrada'] = pd.to_datetime(df_res['entrada'])
        df_f = df_res[(df_res['entrada'].dt.month == m) & (df_res['entrada'].dt.year == a)]
        st.dataframe(df_f, use_container_width=True, hide_index=True)

elif menu == "Despesas":
    st.title("💸 Fluxo de Caixa / Despesas")
    seletor_mes_pro()
    with st.expander("➕ LANÇAR NOVA DESPESA"):
        with st.form("f_desp"):
            d_data = st.date_input("Data do Gasto")
            d_desc = st.text_input("Descrição / Fornecedor")
            d_val = st.number_input("Valor (R$)", 0.0)
            if st.form_submit_button("Registrar Gasto"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d_data), d_desc, d_val])
                st.rerun()
    
    df_d = get_data(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        df_f = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        st.table(df_f[['data', 'descricao', 'valor']])
