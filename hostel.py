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
    button[kind="headerNoContext"] { background-color: #4318FF !important; color: white !important; }
    [data-testid="stMetricValue"] { color: #1B254B !important; font-size: 24px !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    .stButton>button { border-radius: 10px; background: #4318FF; color: white; font-weight: 700; width: 100%; border: none; }
    .btn-delete>button { background: #FF4B4B !important; }
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
    ws_res = spreadsheet.worksheet("reservas")
    ws_des = spreadsheet.worksheet("despesas")
else: st.stop()

def get_data_safe(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️"): st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: st.markdown(f"<h4 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("➡️"): st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- LÓGICA DE EXCLUSÃO/EDIÇÃO GENERICA ---
def delete_row(ws, row_id):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.delete_rows(i + 2) # +2 porque Sheets começa em 1 e tem cabeçalho
            return True
    return False

# --- MÓDULOS ---
if menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    # ... (Gráficos conforme anterior)

elif menu == "📋 Reservas":
    st.title("Gestão de Hóspedes")
    seletor_periodo()
    
    with st.expander("➕ NOVA RESERVA"):
        with st.form("f_res"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome")
            h = c2.number_input("Hóspedes", 1)
            q = c1.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=["Master"])
            en = c2.date_input("Check-in")
            sa = c1.date_input("Check-out")
            vl = c2.number_input("Total R$", 0.0)
            if st.form_submit_button("Salvar"):
                ws_res.append_row([int(datetime.now().timestamp()), n, h, ", ".join(q), str(en), str(sa), (sa-en).days, vl])
                st.rerun()

    df = get_data_safe(ws_res)
    if not df.empty:
        df['entrada_temp'] = pd.to_datetime(df['entrada'])
        df_f = df[(df['entrada_temp'].dt.month == m) & (df['entrada_temp'].dt.year == a)].copy()
        st.dataframe(df_f.drop(columns=['entrada_temp']), use_container_width=True, hide_index=True)
        
        st.divider()
        c_ed1, c_ed2 = st.columns(2)
        with c_ed1:
            res_to_edit = st.selectbox("Editar/Apagar Reserva (ID)", df_f['id'].tolist(), format_func=lambda x: f"ID: {x}")
            if st.button("🗑️ APAGAR RESERVA SELECIONADA", type="secondary"):
                if delete_row(ws_res, res_to_edit): st.success("Apagado!"); st.rerun()

elif menu == "💸 Despesas":
    st.title("Gestão Financeira")
    seletor_periodo()
    with st.expander("➕ NOVA DESPESA"):
        with st.form("f_desp"):
            dt_d = st.date_input("Data")
            ds_d = st.text_input("Descrição")
            vl_d = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Lançar"):
                ws_des.append_row([int(datetime.now().timestamp()), str(dt_d), ds_d, vl_d])
                st.rerun()

    df_d = get_data_safe(ws_des)
    if not df_d.empty:
        df_d['dt_temp'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_temp'].dt.month == m) & (df_d['dt_temp'].dt.year == a)].copy()
        st.dataframe(df_fd.drop(columns=['dt_temp']), use_container_width=True, hide_index=True)
        
        st.divider()
        desp_to_del = st.selectbox("Apagar Despesa (ID)", df_fd['id'].tolist())
        if st.button("🗑️ APAGAR DESPESA"):
            if delete_row(ws_des, desp_to_del): st.success("Removido!"); st.rerun()

elif menu == "📅 Calendário":
    # ... (Código do calendário conforme anterior)
    st.write("Calendário Ativo")
