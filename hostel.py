import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA (UI PREMIUM) ---
st.set_page_config(
    page_title="Hostel Pro | Elite Management", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="auto"
)

# --- INJEÇÃO DE CSS PROFISSIONAL (FIX MOBILE & CONTRASTE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #F4F7FE;
    }

    /* Forçar visibilidade do menu lateral no mobile */
    button[kind="headerNoContext"] {
        background-color: #4318FF !important;
        color: white !important;
        border-radius: 8px !important;
    }

    /* Cards de Métrica - Contraste Absoluto */
    [data-testid="stMetricValue"] {
        color: #1B254B !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #707EAE !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 16px;
        padding: 20px !important;
        box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03);
        border: 1px solid #E9EDF7;
    }

    /* Sidebar Estilizada */
    [data-testid="stSidebar"] { background-color: #111C44; }
    [data-testid="stSidebar"] * { color: #A3AED0 !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 { color: white !important; }
    
    /* Botões Premium */
    .stButton>button {
        border-radius: 10px;
        background: #4318FF;
        color: white;
        font-weight: 700;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: #3311CC;
        box-shadow: 0px 4px 15px rgba(67, 24, 255, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÃO COM GOOGLE SHEETS ---
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
else:
    st.error("Falha na conexão com o Banco de Dados.")
    st.stop()

def get_data_safe(ws):
    df = pd.DataFrame(ws.get_all_records())
    # Normaliza colunas para evitar erros de acentuação/espaços
    df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

# --- COMPONENTES NAVEGAÇÃO ---
def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("⬅️"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with c2:
        st.markdown(f"<h3 style='text-align: center; color: #1B254B;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h3>", unsafe_allow_html=True)
    with c3:
        if st.button("➡️"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()

with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    st.write("---")
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    st.write("---")
    st.caption("v4.0 Elite Edition")

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- LÓGICA DO DASHBOARD ---
if menu == "💰 Dashboard":
    st.markdown("<h2 style='color: #1B254B;'>Business Intelligence</h2>", unsafe_allow_html=True)
    seletor_periodo()
    
    df_r = get_data_safe(ws_reservas)
    df_d = get_data_safe(ws_despesas)
    
    rec, gas = 0, 0
    checkouts_hoje = pd.DataFrame()

    if not df_r.empty:
        df_r['entrada'] = pd.to_datetime(df_r['entrada'])
        df_r['saida'] = pd.to_datetime(df_r['saida'])
        df_mes_r = df_r[(df_r['entrada'].dt.month == m) & (df_r['entrada'].dt.year == a)]
        rec = df_mes_r['total'].sum()
        checkouts_hoje = df_r[df_r['saida'].dt.date == date.today()]

    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
        gas = df_mes_d['valor'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("FATURAMENTO", f"R$ {rec:,.2f}")
    col2.metric("DESPESAS", f"R$ {gas:,.2f}", delta=f"-{gas:,.2f}", delta_color="inverse")
    col3.metric("LUCRO LÍQUIDO", f"R$ {rec-gas:,.2f}")

    if not checkouts_hoje.empty:
        st.warning(f"⚠️ **{len(checkouts_hoje)} Saídas hoje!**")

    # Gráficos com lógica de Múltiplos Quartos
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        st.markdown("<div style='background:white; padding:20px; border-radius:16px; border:1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Receita por Quarto")
        if rec > 0:
            df_exp = df_mes_r.copy()
            df_exp['quarto'] = df_exp['quarto'].astype(str).str.split(', ')
            df_exp = df_exp.explode('quarto')
            # Divide o valor total entre os quartos daquela reserva
            df_exp['pro_rata'] = df_exp['total'] / df_exp['id'].map(df_r.groupby('id')['quarto'].first().str.split(', ').str.len())
            st.bar_chart(df_exp.groupby('quarto')['pro_rata'].sum())
        st.markdown("</div>", unsafe_allow_html=True)
    
    with c_g2:
        st.markdown("<div style='background:white; padding:20px; border-radius:16px; border:1px solid #E9EDF7;'>", unsafe_allow_html=True)
        st.subheader("Balanço Mensal")
        st.area_chart(pd.DataFrame({"Receita": [0, rec], "Despesa": [0, gas]}))
        st.markdown("</div>", unsafe_allow_html=True)

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.markdown("<h2 style='color: #1B254B;'>Mapa de Ocupação</h2>", unsafe_allow_html=True)
    df = get_data_safe(ws_reservas)
    if not df.empty:
        events = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=events, options={"locale":"pt-br", "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}})

# --- RESERVAS (MULTI-QUARTOS) ---
elif menu == "📋 Reservas":
    st.markdown("<h2 style='color: #1B254B;'>Gestão de Hóspedes</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ NOVA RESERVA (MULTI-QUARTOS)"):
        with st.form("f_res"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Hóspede")
            quartos = c2.multiselect("Quartos Selecionados", ["Master", "Studio", "Triplo", "Suíte"], default=["Master"])
            ent = c1.date_input("Check-in")
            sai = c2.date_input("Check-out")
            val = st.number_input("Valor Total", 0.0)
            if st.form_submit_button("Confirmar Reserva"):
                if nome and quartos:
                    ws_reservas.append_row([int(datetime.now().timestamp()), nome, len(quartos), ", ".join(quartos), str(ent), str(sai), (sai-ent).days, val])
                    st.rerun()
    
    df = get_data_safe(ws_reservas)
    if not df.empty:
        df['entrada'] = pd.to_datetime(df['entrada'])
        st.dataframe(df[(df['entrada'].dt.month == m) & (df['entrada'].dt.year == a)], use_container_width=True, hide_index=True)

# --- DESPESAS ---
elif menu == "💸 Despesas":
    st.markdown("<h2 style='color: #1B254B;'>Controle Financeiro</h2>", unsafe_allow_html=True)
    seletor_periodo()
    with st.expander("➕ LANÇAR GASTO"):
        with st.form("f_desp"):
            d_data = st.date_input("Data")
            d_desc = st.text_input("Descrição")
            d_val = st.number_input("Valor", 0.0)
            if st.form_submit_button("Registrar"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(d_data), d_desc, d_val])
                st.rerun()
    
    df_d = get_data_safe(ws_despesas)
    if not df_d.empty:
        df_d['data'] = pd.to_datetime(df_d['data'])
        st.dataframe(df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)], use_container_width=True, hide_index=True)
