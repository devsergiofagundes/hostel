import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro Cloud", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="collapsed" # Melhora a visão inicial no mobile
)

# CSS para forçar ajustes finos em telas pequenas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    @media (max-width: 640px) {
        .stButton button { width: 100%; }
        [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADOS ---
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
        client = gspread.authorize(creds)
        return client
    except:
        st.error("Erro nas credenciais.")
        return None

client = init_connection()
if client:
    spreadsheet = client.open("hostel-db")
    ws_reservas = spreadsheet.worksheet("reservas")
    ws_despesas = spreadsheet.worksheet("despesas")
else:
    st.stop()

def get_data(worksheet):
    return pd.DataFrame(worksheet.get_all_records())

# --- FUNÇÃO POP-UP (DIALOG) ---
@st.dialog("Detalhes")
def detalhes_reserva(event_info):
    st.write(f"### {event_info['title']}")
    st.write(f"📅 **Entrada:** {event_info['start']}")
    st.write(f"🏁 **Saída:** {event_info['end']}")
    if "extendedProps" in event_info:
        p = event_info["extendedProps"]
        st.write(f"👤 **Hóspedes:** {p.get('hospedes')}")
        st.write(f"💰 **Total:** R$ {p.get('total', 0):,.2f}")
    if st.button("Fechar", use_container_width=True):
        st.rerun()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Menu:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- SELETOR DE MÊS RESPONSIVO ---
def seletor_mes():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️", key="prev"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with col2:
        texto = st.session_state.data_filtro.strftime("%b/%y").upper()
        st.markdown(f"<h3 style='text-align: center;'>{texto}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("➡️", key="next"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()

# --- MÓDULO AGENDA ---
if menu == "Agenda":
    st.header("📅 Agenda")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        events = []
        for _, r in df_res.iterrows():
            cor = "#3D5AFE" if r['quarto'] == "Master" else "#00C853" if r['quarto'] == "Studio" else "#FF6D00"
            events.append({
                "title": f"{r['quarto']}-{r['nome']}",
                "start": str(r['entrada']), "end": str(r['saida']), "color": cor,
                "extendedProps": {"hospedes": r['hospedes'], "total": r['total']}
            })
        
        # O calendário se adapta à largura do container automaticamente
        state = calendar(events=events, options={"locale":"pt-br", "initialView":"dayGridMonth"}, key='hostel_calendar')
        
        if state.get("eventClick"):
            event_id = state["eventClick"]["event"]["title"] + state["eventClick"]["event"]["start"]
            if "last_id" not in st.session_state or st.session_state.last_id != event_id:
                st.session_state.last_id = event_id
                detalhes_reserva(state["eventClick"]["event"])
        else: st.session_state.last_id = None

# --- MÓDULO RESERVAS ---
elif menu == "Reservas":
    st.header("📋 Reservas")
    # No mobile, col1 e col2 ficarão um em cima do outro
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.expander("➕ Nova Reserva", expanded=False):
            with st.form("f_res"):
                nome = st.text_input("Hóspede")
                quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
                ent = st.date_input("Check-in")
                sai = st.date_input("Check-out")
                val = st.number_input("Valor", 0.0)
                if st.form_submit_button("Salvar"):
                    ws_reservas.append_row([int(datetime.now().timestamp()), nome, 1, quarto, str(ent), str(sai), 0, val])
                    st.rerun()
    with col2:
        df = get_data(ws_reservas)
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Despesas")
    seletor_mes()
    with st.expander("➕ Lançar Despesa"):
        with st.form("f_desp"):
            d_data = st.date_input("Data")
            d_desc = st.text_input("Descrição")
            d_val = st.number_input("Valor", 0.0)
            if st.form_submit_button("Lançar"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d_data), d_desc, d_val])
                st.rerun()
    
    df_d = get_data(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
        df_f = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        st.dataframe(df_f, use_container_width=True, hide_index=True)

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Financeiro")
    seletor_mes()
    
    m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
    
    # Processamento de dados
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

    # Layout adaptável: métricas que se empilham no mobile
    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", f"R${rec:,.2f}")
    c2.metric("Despesas", f"R${gas:,.2f}")
    c3.metric("Saldo", f"R${rec-gas:,.2f}")
