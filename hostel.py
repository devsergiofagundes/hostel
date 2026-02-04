import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hostel Pro | Management Suite", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="auto"
)

# --- CSS DE ALTO NÍVEL (CORRIGIDO PARA MOBILE E CONTRASTE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #F4F7FE;
    }

    /* Botão de Menu Mobile Visível */
    button[kind="headerNoContext"] {
        background-color: #4318FF !important;
        color: white !important;
    }

    /* Cores das Métricas - Texto Escuro Garantido */
    [data-testid="stMetricValue"] {
        color: #1B254B !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #707EAE !important;
        font-size: 14px !important;
    }
    
    /* Card de Métrica */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 16px;
        padding: 20px !important;
        box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03);
        border: 1px solid #E9EDF7;
    }

    /* Sidebar Dark */
    [data-testid="stSidebar"] { background-color: #111C44; }
    [data-testid="stSidebar"] * { color: #A3AED0 !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 { color: white !important; }
    
    /* Estilo dos Radio Buttons na Navegação */
    div[data-testid="stSidebarNav"] { display: none; } /* Esconde nav padrão */
    
    .stButton>button {
        border-radius: 10px;
        background: #4318FF;
        color: white;
        font-weight: 700;
        width: 100%;
    }
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
    ws_reservas = spreadsheet.worksheet("reservas")
    ws_despesas = spreadsheet.worksheet("despesas")
else: st.stop()

def get_data_safe(ws):
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

# --- UI COMPONENTS ---
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

# --- SIDEBAR COM TODAS AS OPÇÕES ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    st.write("---")
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"], index=0)
    st.write("---")
    st.caption("v3.0 Professional")

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ---
if menu == "💰 Dashboard":
    st.markdown("<h2 style='color: #1B254B;'>Painel de Controlo</h2>", unsafe_allow_html=True)
    seletor_periodo()
    
    df_r = get_data_safe(ws_reservas)
    df_d = get_data_safe(ws_despesas)
    
    rec, gas = 0, 0
    checkouts_hoje = []

    if not df_r.empty:
        df_r['entrada'] = pd.to_datetime(df_r['entrada'])
        df_r['saida'] = pd.to_datetime(df_r['saida'])
        # Receita do mês
        rec = df_r[(df_r['entrada'].dt.month == m) & (df_r['entrada'].dt.year == a)]['total'].sum()
        # Check-outs hoje
        hoje = date.today()
        checkouts_hoje = df_r[df_r['saida'].dt.date == hoje]

    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        gas = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]['valor'].sum()

    # Cards de KPI
    c1, c2, c3 = st.columns(3)
    c1.metric("RECEITA ESTIMADA", f"R$ {rec:,.2f}")
    c2.metric("DESPESAS", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    c3.metric("LUCRO LÍQUIDO", f"R$ {rec-gas:,.2f}")

    # Alerta de Check-outs
    if len(checkouts_hoje) > 0:
        st.warning(f"🔔 **Atenção:** {len(checkouts_hoje)} Check-out(s) para hoje!")
        with st.expander("Ver lista de saídas"):
            st.table(checkouts_hoje[['nome', 'quarto', 'saida']])

    # Gráficos
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("<div style='background:white; p:20px; border-radius:16px; border:1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Ocupação por Quarto")
        if rec > 0:
            st.bar_chart(df_r[(df_r['entrada'].dt.month == m)].groupby('quarto')['total'].sum())
        st.markdown("</div>", unsafe_allow_html=True)
    with col_g2:
        st.markdown("<div style='background:white; p:20px; border-radius:16px; border:1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Fluxo Mensal")
        st.area_chart(pd.DataFrame({"Receita": [0, rec], "Despesa": [0, gas]}))
        st.markdown("</div>", unsafe_allow_html=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.markdown("<h2 style='color: #1B254B;'>Calendário de Ocupação</h2>", unsafe_allow_html=True)
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = [{"title": f"{r['quarto']} - {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=events, options={"locale":"pt-br"})

# --- RESERVAS (CORRIGIDO) ---
elif menu == "📋 Reservas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão de Reservas</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ Nova Reserva"):
        with st.form("f_res"):
            n = st.text_input("Nome")
            q = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            e = st.date_input("Check-in")
            s = st.date_input("Check-out")
            v = st.number_input("Valor Total", 0.0)
            if st.form_submit_button("Guardar"):
                ws_reservas.append_row([int(datetime.now().timestamp()), n, 1, q, str(e), str(s), (s-e).days, v])
                st.rerun()
    df = get_data_safe(ws_reservas)
    if not df.empty:
        df['entrada'] = pd.to_datetime(df['entrada'])
        st.dataframe(df[(df['entrada'].dt.month == m) & (df['entrada'].dt.year == a)], use_container_width=True)

# --- DESPESAS (CORRIGIDO) ---
elif menu == "💸 Despesas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão de Despesas</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ Nova Despesa"):
        with st.form("f_desp"):
            d = st.date_input("Data")
            ds = st.text_input("Descrição")
            vl = st.number_input("Valor", 0.0)
            if st.form_submit_button("Registar"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d), ds, vl])
                st.rerun()
    df_d = get_data_safe(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        st.dataframe(df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)], use_container_width=True)
