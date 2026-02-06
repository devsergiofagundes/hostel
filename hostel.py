import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- 2. LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    with st.form("login_gate"):
        pwd = st.text_input("Senha de Acesso", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == st.secrets["access"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

if not check_password():
    st.stop()

# --- 3. CONEXÃO ---
@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds = Credentials.from_service_account_info(json.loads(json_info), 
                scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão: {e}"); return None

client = init_connection()
spreadsheet = client.open("hostel-db")
ws_res = spreadsheet.worksheet("reservas")
ws_des = spreadsheet.worksheet("despesas")

def get_data(ws):
    data = ws.get_all_records()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
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
            ws.update(f'A{i+2}:I{i+2}', [new_data])
            return True
    return False

# --- 4. NAVEGAÇÃO ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

with st.sidebar:
    st.markdown("## HOSTEL PRO")
    menu = st.radio("MENU", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    if st.button("Sair"):
        st.session_state["password_correct"] = False
        st.rerun()

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year

def seletor_periodo():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("⬅️"): st.session_state.data_filtro -= pd.DateOffset(months=1); st.rerun()
    with c2: st.markdown(f"<h4 style='text-align: center;'>{st.session_state.data_filtro.strftime('%B %Y').upper()}</h4>", unsafe_allow_html=True)
    with c3: 
        if st.button("➡️"): st.session_state.data_filtro += pd.DateOffset(months=1); st.rerun()

# --- 5. MÓDULOS ---

if menu == "💰 Dashboard":
    st.title("BI Dashboard")
    seletor_periodo()
    df_r, df_d = get_data(ws_res), get_data(ws_des)
    bruto, taxas, operacionais = 0.0, 0.0, 0.0
    df_mes_r = pd.DataFrame()

    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        if not df_mes_r.empty:
            bruto = df_mes_r['total'].sum()
            tax_b = df_mes_r[df_mes_r['origem'] == 'Booking']['total'].sum() * 0.18
            tax_d = df_mes_r[df_mes_r['origem'].isin(['Telefone', 'Whatsapp'])]['total'].sum() * 0.05
            taxas = tax_b + tax_d

    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        operacionais = df_mes_d['valor'].sum()

    liquido = bruto - taxas - operacionais

    # MÉTRICAS DO MÊS FECHADO (PROJEÇÃO)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PROJEÇÃO BRUTO", f"R$ {bruto:,.2f}")
    c2.metric("PROJEÇÃO TAXAS", f"R$ {taxas:,.2f}")
    c3.metric("PROJEÇÃO DESPESAS", f"R$ {operacionais:,.2f}")
    c4.metric("PROJEÇÃO LUCRO", f"R$ {liquido:,.2f}")

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    with cg1:
        st.subheader("Ocupação por Quarto")
        if not df_mes_r.empty:
            df_plot = df_mes_r.copy()
            df_plot['quarto'] = df_plot['quarto'].astype(str).str.split(', ')
            st.bar_chart(df_plot.explode('quarto').groupby('quarto')['total'].count())
    with cg2:
        st.subheader("Divisão Financeira")
        if bruto > 0:
            fin_df = pd.DataFrame({"Cat": ["Taxas", "Despesas", "Lucro"], "Val": [taxas, operacionais, max(0, liquido)]})
            st.bar_chart(fin_df.set_index("Cat"))

    # --- SEÇÃO RESTAURADA: FINANÇAS ATÉ HOJE ---
    st.markdown("---")
    st.subheader(f"📊 Realizado: 01/{m:02d}/{a} até {date.today().strftime('%d/%m/%Y')}")
    
    hoje = date.today()
    br_h, tx_h, op_h = 0.0, 0.0, 0.0

    if not df_mes_r.empty:
        df_h_r = df_mes_r[df_mes_r['en_dt'].dt.date <= hoje]
        br_h = df_h_r['total'].sum()
        tx_h = (df_h_r[df_h_r['origem'] == 'Booking']['total'].sum() * 0.18) + (df_h_r[df_h_r['origem'].isin(['Telefone', 'Whatsapp'])]['total'].sum() * 0.05)

    if not df_d.empty:
        df_h_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a) & (df_d['dt_dt'].dt.date <= hoje)]
        op_h = df_h_d['valor'].sum()

    ch1, ch2, ch3, ch4 = st.columns(4)
    ch1.metric("BRUTO REALIZADO", f"R$ {br_h:,.2f}")
    ch2.metric("TAXAS PAGAS", f"R$ {tx_h:,.2f}")
    ch3.metric("DESPESAS PAGAS", f"R$ {op_h:,.2f}")
    ch4.metric("LUCRO REAL", f"R$ {(br_h - tx_h - op_h):,.2f}")

elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    seletor_periodo()
    
    if "edit_mode" in st.session_state and st.session_state.edit_mode:
        with st.container(border=True):
            mode, data = st.session_state.edit_mode, st.session_state.item_selecionado
            with st.form("form_r"):
                c1, c2, c3 = st.columns([2, 1, 1])
                nome = c1.text_input("Nome", value=data['nome'] if data is not None else "")
                hosp = c2.number_input("Hóspedes", min_value=1, value=int(data['hospedes']) if data is not None else 1)
                orig = c3.selectbox("Origem", ["Booking", "Telefone", "Whatsapp"], index=0)
                c4, c5, c6, c7 = st.columns(4)
                q_at = str(data['quarto']).split(", ") if data is not None else ["Master"]
                quartos = c4.multiselect("Quartos", ["Master", "Studio", "Triplo"], q_at)
                ent = c5.date_input("Check-in", value=pd.to_datetime(data['entrada']) if data is not None else date.today())
                sai = c6.date_input("Check-out", value=pd.to_datetime(data['saida']) if data is not None else date.today())
                val = c7.number_input("Total R$", value=float(data['total']) if data is not None else 0.0)
                if st.form_submit_button("✅ SALVAR"):
                    new = [data['id'] if mode=="editar" else int(datetime.now().timestamp()), nome, hosp, ", ".join(quartos), str(ent), str(sai), (sai-ent).days, val, orig]
                    if mode=="editar": update_row(ws_res, data['id'], new)
                    else: ws_res.append_row(new)
                    st.session_state.edit_mode = None; st.rerun()
                if st.form_submit_button("❌ CANCELAR"): st.session_state.edit_mode = None; st.rerun()

    if not st.session_state.get("edit_mode"):
        if st.button("➕ Nova Reserva"): 
            st.session_state.edit_mode = "novo"; st.session_state.item_selecionado = None; st.rerun()

    df_r = get_data(ws_res)
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy().sort_values(by='en_dt', ascending=False)
        st.markdown("---")
        h_cols = st.columns([0.8, 3, 2, 2, 1.5, 0.6, 0.6])
        for col, label in zip(h_cols, ["ID", "Hóspede", "Entrada", "Quarto", "Total", "📝", "🗑️"]): col.markdown(f"**{label}**")
        st.divider()
        for _, row in df_f.iterrows():
            cols = st.columns([0.8, 3, 2, 2, 1.5, 0.6, 0.6])
            cols[0].write(f"`{str(row['id'])[-4:]}`")
            cols[1].write(row['nome'])
            cols[2].write(pd.to_datetime(row['entrada']).strftime('%d/%m/%Y'))
            cols[3].write(row['quarto'])
            cols[4].write(f"R$ {row['total']:,.2f}")
            if cols[5].button("📝", key=f"e_{row['id']}"):
                st.session_state.edit_mode = "editar"; st.session_state.item_selecionado = row; st.rerun()
            if cols[6].button("🗑️", key=f"d_{row['id']}"): delete_by_id(ws_res, row['id']); st.rerun()

elif menu == "💸 Despesas":
    st.title("Gestão de Despesas")
    seletor_periodo()
    if "edit_mode_d" in st.session_state and st.session_state.edit_mode_d:
        with st.container(border=True):
            data_d = st.session_state.item_selecionado_d
            with st.form("form_d"):
                c1, c2, c3 = st.columns([1, 2, 1])
                dt_p = c1.date_input("Data", value=pd.to_datetime(data_d['data']) if data_d is not None else date.today())
                ds_p = c2.text_input("Descrição", value=data_d['descricao'] if data_d is not None else "")
                vl_p = c3.number_input("Valor", value=float(data_d['valor']) if data_d is not None else 0.0)
                if st.form_submit_button("✅ SALVAR"):
                    row_id = data_d['id'] if st.session_state.edit_mode_d == "editar" else int(datetime.now().timestamp())
                    if st.session_state.edit_mode_d == "editar": update_row(ws_des, row_id, [row_id, str(dt_p), ds_p, vl_p])
                    else: ws_des.append_row([row_id, str(dt_p), ds_p, vl_p])
                    st.session_state.edit_mode_d = None; st.rerun()
                if st.form_submit_button("❌ CANCELAR"): st.session_state.edit_mode_d = None; st.rerun()

    if not st.session_state.get("edit_mode_d"):
        if st.button("➕ Nova Despesa"): 
            st.session_state.edit_mode_d = "novo"; st.session_state.item_selecionado_d = None; st.rerun()

    df_d = get_data(ws_des)
    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy().sort_values(by='dt_dt', ascending=False)
        st.markdown("---")
        h_cols_d = st.columns([1, 2, 4, 2, 0.6, 0.6])
        for col, label in zip(h_cols_d, ["ID", "Data", "Descrição", "Valor", "📝", "🗑️"]): col.markdown(f"**{label}**")
        st.divider()
        for _, row in df_fd.iterrows():
            cols = st.columns([1, 2, 4, 2, 0.6, 0.6])
            cols[0].write(f"`{str(row['id'])[-4:]}`")
            cols[1].write(pd.to_datetime(row['data']).strftime('%d/%m/%Y'))
            cols[2].write(row['descricao'])
            cols[3].write(f"R$ {row['valor']:,.2f}")
            if cols[4].button("📝", key=f"ed_{row['id']}"):
                st.session_state.edit_mode_d = "editar"; st.session_state.item_selecionado_d = row; st.rerun()
            if cols[5].button("🗑️", key=f"dd_{row['id']}"): delete_by_id(ws_des, row['id']); st.rerun()

elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
