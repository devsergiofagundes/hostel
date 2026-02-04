import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- 2. SISTEMA DE LOGIN SEGURO (Via Secrets) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.markdown("""
        <div style='text-align: center; padding: 50px;'>
            <h1>🏨 Hostel Pro | Elite</h1>
            <p>Acesso restrito ao administrador</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_gate"):
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.form_submit_button("Entrar no Sistema"):
            if pwd == st.secrets["access"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

if not check_password():
    st.stop()

# --- 3. CSS PREMIUM ATUALIZADO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #F4F7FE; }
    
    /* Botões Principais */
    .stButton>button {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        border: none !important;
        box-shadow: 0px 4px 12px rgba(67, 24, 255, 0.2) !important;
    }
    
    /* Botão de Apagar (Vermelho) */
    div.stButton > button:contains("APAGAR") {
        background-color: #FF4B4B !important;
        box-shadow: 0px 4px 12px rgba(255, 75, 75, 0.2) !important;
    }

    [data-testid="stMetricValue"] { color: #1B254B !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0,0,0,0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    [data-testid="stSidebar"] * { color: #A3AED0 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. CONEXÃO E FUNÇÕES ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds = Credentials.from_service_account_info(json.loads(json_info), 
                scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

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

# --- 5. NAVEGAÇÃO E SELETOR ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: white;'>HOSTEL PRO</h2>", unsafe_allow_html=True)
    menu = st.radio("MENU", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    if st.button("Sair (Logout)"):
        st.session_state["password_correct"] = False
        st.rerun()

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️ Anterior"): 
            st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: 
        st.markdown(f"<h4 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3:
        if st.button("Próximo ➡️"): 
            st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- 6. MÓDULOS ---

if menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    df_r, df_d = get_data(ws_res), get_data(ws_des)
    bruto, taxas, operacionais = 0.0, 0.0, 0.0
    df_mes_r = pd.DataFrame()

    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        bruto = df_mes_r['total'].sum()
        taxas = bruto * 0.18

    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        operacionais = df_mes_d['valor'].sum()

    liquido = bruto - taxas - operacionais

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BRUTO", f"R$ {bruto:,.2f}")
    c2.metric("TAXAS (18%)", f"R$ {taxas:,.2f}", delta_color="inverse")
    c3.metric("DESPESAS", f"R$ {operacionais:,.2f}")
    c4.metric("LUCRO REAL", f"R$ {liquido:,.2f}")

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    with cg1:
        st.subheader("Ocupação por Quarto")
        if not df_mes_r.empty:
            df_plot = df_mes_r.copy()
            df_plot['quarto'] = df_plot['quarto'].astype(str).str.split(', ')
            df_exploded = df_plot.explode('quarto')
            st.bar_chart(df_exploded.groupby('quarto')['total'].count())
        else: st.info("Sem dados.")
    with cg2:
        st.subheader("Divisão de Custos")
        if bruto > 0:
            df_custos = pd.DataFrame({"Valor": [taxas, operacionais, liquido]}, index=["Taxas", "Operacional", "Lucro"])
            st.bar_chart(df_custos)

elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    seletor_periodo()
    df_r = get_data(ws_res)
    df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
    df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()
    
    t1, t2 = st.tabs(["➕ Nova", "⚙️ Gerenciar"])
    with t1:
        with st.form("add_r"):
            nome = st.text_input("Hóspede")
            q = st.multiselect("Quartos", ["Master", "Studio", "Triplo"], ["Master"])
            en, sa = st.columns(2)
            ent = en.date_input("Check-in")
            sai = sa.date_input("Check-out")
            val = st.number_input("Total Bruto R$", 0.0)
            if st.form_submit_button("Salvar"):
                ws_res.append_row([int(datetime.now().timestamp()), nome, 1, ", ".join(q), str(ent), str(sai), (sai-ent).days, val])
                st.rerun()
    with t2:
        if not df_f.empty:
            id_s = st.selectbox("Selecione ID para apagar", df_f['id'].tolist())
            if st.button("🗑️ APAGAR RESERVA SELECIONADA"):
                delete_by_id(ws_res, id_s); st.rerun()
    
    st.dataframe(df_f.drop(columns=['en_dt']), use_container_width=True, hide_index=True)

elif menu == "💸 Despesas":
    st.title("Gestão de Despesas")
    seletor_periodo()
    df_d = get_data(ws_des)
    df_d['dt_dt'] = pd.to_datetime(df_d['data'])
    df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()
    
    t1, t2 = st.tabs(["➕ Nova", "⚙️ Gerenciar"])
    with t1:
        with st.form("add_d"):
            dt = st.date_input("Data")
            ds = st.text_input("Descrição")
            vl = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Lançar"):
                ws_des.append_row([int(datetime.now().timestamp()), str(dt), ds, vl])
                st.rerun()
    with t2:
        if not df_fd.empty:
            id_d = st.selectbox("Selecione ID para apagar", df_fd['id'].tolist())
            if st.button("🗑️ APAGAR DESPESA SELECIONADA"):
                delete_by_id(ws_des, id_d); st.rerun()

    st.dataframe(df_fd.drop(columns=['dt_dt']), use_container_width=True, hide_index=True)

elif menu == "📅 Calendário":
    st.title("Calendário")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
