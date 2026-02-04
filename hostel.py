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
    initial_sidebar_state="collapsed"
)

# CSS para melhor visualização em Mobile
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stButton button { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO GLOBAL DE DATA ---
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
        st.error("Erro ao conectar ao Google Sheets.")
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

# --- COMPONENTE DE SELEÇÃO DE MÊS ---
def seletor_mes():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️", key="prev"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with col2:
        texto = st.session_state.data_filtro.strftime("%b / %Y").upper()
        st.markdown(f"<h3 style='text-align: center;'>{texto}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("➡️", key="next"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()
    st.divider()

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
        state = calendar(events=events, options={"locale":"pt-br", "initialView":"dayGridMonth"}, key='hostel_calendar')
        if state.get("eventClick"):
            event_id = state["eventClick"]["event"]["title"] + state["eventClick"]["event"]["start"]
            if "last_id" not in st.session_state or st.session_state.last_id != event_id:
                st.session_state.last_id = event_id
                detalhes_reserva(state["eventClick"]["event"])
        else: st.session_state.last_id = None

# --- MÓDULO RESERVAS ---
elif menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    seletor_mes()
    
    with st.expander("➕ Nova Reserva", expanded=False):
        with st.form("f_res", clear_on_submit=True):
            nome = st.text_input("Hóspede")
            hosp = st.number_input("Hóspedes", 1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            ent = st.date_input("Check-in")
            sai = st.date_input("Check-out")
            val = st.number_input("Valor Total", 0.0)
            if st.form_submit_button("Salvar Reserva"):
                diarias = (sai - ent).days
                if diarias > 0:
                    ws_reservas.append_row([int(datetime.now().timestamp()), nome, hosp, quarto, str(ent), str(sai), diarias, val])
                    st.success("Reserva salva!")
                    st.rerun()
                else: st.error("Data de saída inválida.")

    df_res = get_data(ws_reservas)
    if not df_res.empty:
        df_res['entrada'] = pd.to_datetime(df_res['entrada'])
        m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
        df_f = df_res[(df_res['entrada'].dt.month == m) & (df_res['entrada'].dt.year == a)]
        
        st.subheader(f"Reservas de {st.session_state.data_filtro.strftime('%B/%Y')}")
        st.dataframe(df_f, use_container_width=True, hide_index=True)
        
        if not df_f.empty:
            id_del = st.selectbox("Eliminar Reserva (Selecionar ID):", df_f['id'].tolist())
            if st.button("🗑️ Eliminar Selecionada"):
                cell = ws_reservas.find(str(id_del))
                ws_reservas.delete_rows(cell.row)
                st.rerun()

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
        st.metric("Total Gasto", f"R$ {df_f['valor'].sum():,.2f}")

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Financeiro")
    seletor_mes()
    m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
    
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
    col1.metric("Receitas", f"R${rec:,.2f}")
    col2.metric("Despesas", f"R${gas:,.2f}", delta=-gas)
    col3.metric("Saldo", f"R${rec-gas:,.2f}")
