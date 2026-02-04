import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- CSS PREMIUM (BOTÕES COLORIDOS E CONTRASTE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #F4F7FE; }
    
    /* Botões Padrão (Azul Indigo) */
    .stButton>button {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
        font-weight: 700 !important;
        box-shadow: 0px 4px 12px rgba(67, 24, 255, 0.2) !important;
    }
    
    /* Botão de Apagar (Vermelho) */
    .btn-delete > div > button {
        background-color: #FF4B4B !important;
        color: white !important;
    }

    [data-testid="stMetricValue"] { color: #1B254B !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0,0,0,0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    [data-testid="stSidebar"] * { color: #A3AED0 !important; }
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

# --- DASHBOARD ---
if menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    df_r = get_data(ws_res)
    df_d = get_data(ws_des)
    rec, gas = 0.0, 0.0
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        rec = df_mes_r['total'].sum()
    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        gas = df_mes_d['valor'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("RECEITA", f"R$ {rec:,.2f}")
    c2.metric("DESPESAS", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    c3.metric("LUCRO", f"R$ {rec-gas:,.2f}")

# --- RESERVAS (FILTRADAS POR MÊS) ---
elif menu == "📋 Reservas":
    st.title("Gestão de Hóspedes")
    seletor_periodo()
    df_r = get_data(ws_res)
    df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
    df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()

    tab1, tab2 = st.tabs(["➕ Nova Reserva", "⚙️ Gerenciar (Editar/Apagar)"])
    
    with tab1:
        with st.form("f_nova_res"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome")
            hosp = c2.number_input("Hóspedes", 1)
            quar = c1.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=["Master"])
            en_in = c2.date_input("Check-in")
            sa_in = c1.date_input("Check-out")
            v_in = c2.number_input("Total R$", 0.0)
            if st.form_submit_button("Confirmar Reserva"):
                ws_res.append_row([int(datetime.now().timestamp()), nome, hosp, ", ".join(quar), str(en_in), str(sa_in), (sa_in-en_in).days, v_in])
                st.rerun()

    with tab2:
        if not df_f.empty:
            id_sel = st.selectbox("Selecione ID para Editar/Apagar", df_f['id'].tolist())
            row = df_f[df_f['id'] == id_sel].iloc[0]
            with st.form("f_edit_res"):
                en_e = st.date_input("Check-in", value=pd.to_datetime(row['entrada']).date())
                sa_e = st.date_input("Check-out", value=pd.to_datetime(row['saida']).date())
                vl_e = st.number_input("Valor", value=float(row['total']))
                if st.form_submit_button("💾 Atualizar"):
                    update_row(ws_res, id_sel, [id_sel, row['nome'], row['hospedes'], row['quarto'], str(en_e), str(sa_e), (sa_e-en_e).days, vl_e])
                    st.rerun()
            st.markdown('<div class="btn-delete">', unsafe_allow_html=True)
            if st.button("🗑️ APAGAR RESERVA SELECIONADA", use_container_width=True):
                delete_by_id(ws_res, id_sel); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.subheader(f"Registos de {st.session_state.data_filtro.strftime('%B %Y')}")
    st.dataframe(df_f.drop(columns=['en_dt']), use_container_width=True, hide_index=True)

# --- DESPESAS (FILTRADAS POR MÊS) ---
elif menu == "💸 Despesas":
    st.title("Gestão Financeira")
    seletor_periodo()
    df_d = get_data(ws_des)
    df_d['dt_dt'] = pd.to_datetime(df_d['data'])
    df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()

    tab1, tab2 = st.tabs(["➕ Lançar", "⚙️ Gerenciar"])
    
    with tab1:
        with st.form("f_nova_des"):
            d_dt = st.date_input("Data")
            d_ds = st.text_input("Descrição")
            d_vl = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Lançar"):
                ws_des.append_row([int(datetime.now().timestamp()), str(d_dt), d_ds, d_vl])
                st.rerun()

    with tab2:
        if not df_fd.empty:
            id_d = st.selectbox("Selecione ID", df_fd['id'].tolist())
            row_d = df_fd[df_fd['id'] == id_d].iloc[0]
            with st.form("f_edit_des"):
                ed_dt = st.date_input("Data", value=pd.to_datetime(row_d['data']).date())
                ed_ds = st.text_input("Descrição", value=row_d['descricao'])
                ed_vl = st.number_input("Valor", value=float(row_d['valor']))
                if st.form_submit_button("💾 Atualizar"):
                    update_row(ws_des, id_d, [id_d, str(ed_dt), ed_ds, ed_vl], cols="D")
                    st.rerun()
            st.markdown('<div class="btn-delete">', unsafe_allow_html=True)
            if st.button("🗑️ APAGAR DESPESA", use_container_width=True):
                delete_by_id(ws_des, id_d); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.subheader(f"Gastos de {st.session_state.data_filtro.strftime('%B %Y')}")
    st.dataframe(df_fd.drop(columns=['dt_dt']), use_container_width=True, hide_index=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada'])[:10], "end": str(r['saida'])[:10], "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs, options={"locale":"pt-br"})
