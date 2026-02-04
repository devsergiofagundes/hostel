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
    [data-testid="stMetricValue"] { color: #1B254B !important; font-size: 24px !important; font-weight: 700 !important; }
    div[data-testid="stMetric"] { background-color: white; border-radius: 16px; padding: 20px !important; box-shadow: 0px 10px 30px rgba(0, 0, 0, 0.03); border: 1px solid #E9EDF7; }
    [data-testid="stSidebar"] { background-color: #111C44; }
    .stButton>button { border-radius: 10px; background: #4318FF; color: white; font-weight: 700; width: 100%; }
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

# --- FUNÇÕES DE BANCO ---
def delete_by_id(ws, row_id):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.delete_rows(i + 2)
            return True
    return False

def update_reserva(ws, row_id, lista_dados):
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.update(f'A{i+2}:H{i+2}', [lista_dados])
            return True
    return False

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>HOSTEL PRO</h1>", unsafe_allow_html=True)
    menu = st.radio("NAVEGAÇÃO", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

# --- DASHBOARD ---
if menu == "💰 Dashboard":
    st.title("Business Intelligence")
    seletor_periodo()
    df_r = get_data_safe(ws_res)
    df_d = get_data_safe(ws_des)
    rec, gas = 0, 0
    if not df_r.empty:
        df_r['entrada_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['entrada_dt'].dt.month == m) & (df_r['entrada_dt'].dt.year == a)]
        rec = df_mes_r['total'].sum()
    if not df_d.empty:
        df_d['data_dt'] = pd.to_datetime(df_d['data'])
        gas = df_d[(df_d['data_dt'].dt.month == m) & (df_d['data_dt'].dt.year == a)]['valor'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("RECEITA", f"R$ {rec:,.2f}")
    c2.metric("DESPESAS", f"R$ {gas:,.2f}")
    c3.metric("LUCRO", f"R$ {rec-gas:,.2f}")
    
    cg1, cg2 = st.columns(2)
    with cg1: st.subheader("Ocupação por Quarto"); st.bar_chart(df_r.groupby('quarto')['total'].sum()) if not df_r.empty else st.info("Sem dados")
    with cg2: st.subheader("Fluxo Caixa"); st.area_chart(pd.DataFrame({"Rec": [0, rec], "Gas": [0, gas]}))

# --- CALENDÁRIO ---
elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data_safe(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada'])[:10], "end": str(r['saida'])[:10], "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs, options={"locale":"pt-br"})

# --- RESERVAS (COM EDITAR E APAGAR) ---
elif menu == "📋 Reservas":
    st.title("Gestão de Hóspedes")
    seletor_periodo()
    df = get_data_safe(ws_res)
    
    with st.expander("➕ NOVA RESERVA / EDITAR"):
        id_edit = st.selectbox("Selecione ID para EDITAR (ou 'Novo')", ["Novo"] + df['id'].tolist() if not df.empty else ["Novo"])
        
        # Preenchimento automático se for edição
        default_data = {"n": "", "h": 1, "q": ["Master"], "en": date.today(), "sa": date.today(), "vl": 0.0}
        if id_edit != "Novo":
            row = df[df['id'] == id_edit].iloc[0]
            default_data = {"n": row['nome'], "h": int(row['hospedes']), "q": str(row['quarto']).split(", "), 
                            "en": pd.to_datetime(row['entrada']).date(), "sa": pd.to_datetime(row['saida']).date(), "vl": float(row['total'])}

        with st.form("f_res"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome", value=default_data["n"])
            h = c2.number_input("Hóspedes", min_value=1, value=default_data["h"])
            q = c1.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=default_data["q"])
            en = c2.date_input("Check-in", value=default_data["en"])
            sa = c1.date_input("Check-out", value=default_data["sa"])
            vl = c2.number_input("Total R$", value=default_data["vl"])
            
            if st.form_submit_button("SALVAR ALTERAÇÕES" if id_edit != "Novo" else "CRIAR RESERVA"):
                diarias = (sa - en).days
                dados = [id_edit if id_edit != "Novo" else int(datetime.now().timestamp()), n, h, ", ".join(q), str(en), str(sa), diarias, vl]
                if id_edit != "Novo": update_reserva(ws_res, id_edit, dados)
                else: ws_res.append_row(dados)
                st.rerun()

    if not df.empty:
        df['entrada_temp'] = pd.to_datetime(df['entrada'])
        df_f = df[(df['entrada_temp'].dt.month == m) & (df['entrada_temp'].dt.year == a)].copy()
        st.dataframe(df_f.drop(columns=['entrada_temp']), use_container_width=True, hide_index=True)
        
        st.divider()
        res_del = st.selectbox("ID para APAGAR", df_f['id'].tolist())
        if st.button("🗑️ APAGAR DEFINITIVAMENTE"):
            if delete_by_id(ws_res, res_del): st.rerun()

# --- DESPESAS (COM EDITAR E APAGAR) ---
elif menu == "💸 Despesas":
    st.title("Gestão Financeira")
    seletor_periodo()
    df_d = get_data_safe(ws_des)
    
    with st.expander("➕ LANÇAR / EDITAR DESPESA"):
        id_d_edit = st.selectbox("Editar ID", ["Novo"] + df_d['id'].tolist() if not df_d.empty else ["Novo"])
        d_def = {"dt": date.today(), "ds": "", "vl": 0.0}
        if id_d_edit != "Novo":
            r_d = df_d[df_d['id'] == id_d_edit].iloc[0]
            d_def = {"dt": pd.to_datetime(r_d['data']).date(), "ds": r_d['descricao'], "vl": float(r_d['valor'])}

        with st.form("f_des"):
            dt_d = st.date_input("Data", value=d_def["dt"])
            ds_d = st.text_input("Descrição", value=d_def["ds"])
            vl_d = st.number_input("Valor R$", value=d_def["vl"])
            if st.form_submit_button("SALVAR"):
                dados_d = [id_d_edit if id_d_edit != "Novo" else int(datetime.now().timestamp()), str(dt_d), ds_d, vl_d]
                if id_d_edit != "Novo": delete_by_id(ws_des, id_d_edit); ws_des.append_row(dados_d) # Update simplificado
                else: ws_des.append_row(dados_d)
                st.rerun()

    if not df_d.empty:
        df_d['dt_t'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_t'].dt.month == m) & (df_d['dt_t'].dt.year == a)].copy()
        st.dataframe(df_fd.drop(columns=['dt_t']), use_container_width=True, hide_index=True)
        if st.button("🗑️ APAGAR SELECIONADO"): delete_by_id(ws_des, id_d_edit); st.rerun()
