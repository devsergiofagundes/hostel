import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #F4F7FE; }
    [data-testid="stMetricValue"] { color: #1B254B !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0,0,0,0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #F4F7FE; border-radius: 4px; border: none; }
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

def update_row(ws, row_id, new_data):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.update(f'A{i+2}:H{i+2}', [new_data])
            return True
    return False

# --- UI ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: white;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️"): st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: st.markdown(f"<h4 style='text-align: center;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("➡️"): st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- MÓDULO DESPESAS (TOTALMENTE CORRIGIDO) ---
if menu == "💸 Despesas":
    st.title("Gestão Financeira")
    seletor_periodo()
    
    tab1, tab2 = st.tabs(["➕ Lançar Novo", "⚙️ Gerenciar (Editar/Apagar)"])
    
    df_d = get_data(ws_des)
    
    with tab1:
        with st.form("f_nova_desp"):
            d_dt = st.date_input("Data")
            d_ds = st.text_input("Descrição")
            d_vl = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Lançar"):
                ws_des.append_row([int(datetime.now().timestamp()), str(d_dt), d_ds, d_vl])
                st.rerun()

    with tab2:
        if not df_d.empty:
            id_sel = st.selectbox("Selecione a Despesa pelo ID", df_d['id'].tolist())
            row_d = df_d[df_d['id'] == id_sel].iloc[0]
            
            with st.form("f_edit_desp"):
                e_dt = st.date_input("Nova Data", value=pd.to_datetime(row_d['data']).date())
                e_ds = st.text_input("Nova Descrição", value=row_d['descricao'])
                e_vl = st.number_input("Novo Valor", value=float(row_d['valor']))
                
                c_bt1, c_bt2 = st.columns(2)
                if c_bt1.form_submit_button("💾 Salvar Alterações"):
                    update_row(ws_des, id_sel, [id_sel, str(e_dt), e_ds, e_vl])
                    st.rerun()
                
            if st.button("🗑️ APAGAR ESTA DESPESA", use_container_width=True):
                if delete_by_id(ws_des, id_sel): st.rerun()

    # Visualização da Tabela
    if not df_d.empty:
        df_d['dt_t'] = pd.to_datetime(df_d['data'])
        st.dataframe(df_d[(df_d['dt_t'].dt.month == m) & (df_d['dt_t'].dt.year == a)].drop(columns=['dt_t']), use_container_width=True, hide_index=True)

# --- MÓDULO RESERVAS (ORGANIZADO) ---
elif menu == "📋 Reservas":
    st.title("Gestão de Hóspedes")
    seletor_periodo()
    tab_r1, tab_r2 = st.tabs(["➕ Nova Reserva", "⚙️ Gerenciar"])
    
    df_r = get_data(ws_res)
    
    with tab_r1:
        with st.form("f_nova_res"):
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

    with tab_r2:
        if not df_r.empty:
            id_r_sel = st.selectbox("Selecione Reserva pelo ID", df_r['id'].tolist())
            row_r = df_r[df_r['id'] == id_r_sel].iloc[0]
            with st.form("f_edit_res"):
                en_e = st.date_input("Check-in", value=pd.to_datetime(row_r['entrada']).date())
                sa_e = st.date_input("Check-out", value=pd.to_datetime(row_r['saida']).date())
                if st.form_submit_button("💾 Atualizar Reserva"):
                    update_row(ws_res, id_r_sel, [id_r_sel, row_r['nome'], row_r['hospedes'], row_r['quarto'], str(en_e), str(sa_e), (sa_e-en_e).days, row_r['total']])
                    st.rerun()
            if st.button("🗑️ APAGAR RESERVA"):
                delete_by_id(ws_res, id_r_sel); st.rerun()

    if not df_r.empty:
        df_r['en_t'] = pd.to_datetime(df_r['entrada'])
        st.dataframe(df_r[(df_r['en_t'].dt.month == m) & (df_r['en_t'].dt.year == a)].drop(columns=['en_t']), use_container_width=True, hide_index=True)

# --- DASHBOARD & CALENDÁRIO ---
elif menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    df_r, df_d = get_data(ws_res), get_data(ws_des)
    # Lógica de soma e métricas...
    st.metric("Total Receita", f"R$ {df_r['total'].sum() if not df_r.empty else 0}")

elif menu == "📅 Calendário":
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida'])} for _, r in df.iterrows()]
        calendar(events=evs)
