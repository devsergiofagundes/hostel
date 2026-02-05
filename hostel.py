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
            # A planilha começa na linha 2 (1 é cabeçalho)
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
            if 'origem' in df_mes_r.columns:
                tax_b = df_mes_r[df_mes_r['origem'] == 'Booking']['total'].sum() * 0.18
                tax_t = df_mes_r[df_mes_r['origem'] == 'Telefone']['total'].sum() * 0.05
                taxas = tax_b + tax_t
            else: taxas = bruto * 0.18

    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
        operacionais = df_mes_d['valor'].sum()

    liquido = bruto - taxas - operacionais

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BRUTO", f"R$ {bruto:,.2f}")
    c2.metric("TAXAS", f"R$ {taxas:,.2f}")
    c3.metric("DESPESAS", f"R$ {operacionais:,.2f}")
    c4.metric("LUCRO REAL", f"R$ {liquido:,.2f}")

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    with cg1:
        st.subheader("Ocupação")
        if not df_mes_r.empty:
            st.bar_chart(df_mes_r.groupby('quarto')['total'].count())
        else: st.info("Sem dados")
    with cg2:
        st.subheader("Divisão Financeira")
        if bruto > 0:
            st.bar_chart(pd.DataFrame({"Valor": [taxas, operacionais, liquido]}, index=["Taxas", "Operacional", "Lucro"]))

elif menu == "📋 Reservas":
    st.title("Reservas")
    seletor_periodo()
    df_r = get_data(ws_res)
    df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
    df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()

    t1, t2, t3 = st.tabs(["➕ Nova", "✏️ Editar", "🗑️ Apagar"])
    
    with t1:
        with st.form("add_r"):
            nome = st.text_input("Hóspede")
            q = st.multiselect("Quartos", ["Master", "Studio", "Triplo"], ["Master"])
            en, sa = st.columns(2)
            ent, sai = en.date_input("In"), sa.date_input("Out")
            origem = st.selectbox("Origem", ["Booking", "Telefone"])
            val = st.number_input("Valor R$", 0.0)
            if st.form_submit_button("Salvar"):
                ws_res.append_row([int(datetime.now().timestamp()), nome, 1, ", ".join(q), str(ent), str(sai), (sai-ent).days, val, origem])
                st.rerun()

    with t2:
        if not df_f.empty:
            id_edit = st.selectbox("ID para Editar", df_f['id'].tolist(), key="edit_res")
            res_data = df_f[df_f['id'] == id_edit].iloc[0]
            with st.form("edit_r_form"):
                en_e, sa_e = st.columns(2)
                nome_e = st.text_input("Nome", value=res_data['nome'])
                ent_e = en_e.date_input("In", value=pd.to_datetime(res_data['entrada']))
                sai_e = sa_e.date_input("Out", value=pd.to_datetime(res_data['saida']))
                origem_e = st.selectbox("Origem", ["Booking", "Telefone"], index=0 if res_data['origem'] == 'Booking' else 1)
                val_e = st.number_input("Valor", value=float(res_data['total']))
                if st.form_submit_button("Atualizar"):
                    new_row = [int(id_edit), nome_e, 1, res_data['quarto'], str(ent_e), str(sai_e), (sai_e-ent_e).days, val_e, origem_e]
                    update_row(ws_res, id_edit, new_row)
                    st.rerun()

    with t3:
        if not df_f.empty:
            id_del = st.selectbox("ID para Apagar", df_f['id'].tolist())
            if st.button("CONFIRMAR EXCLUSÃO"):
                delete_by_id(ws_res, id_del); st.rerun()

    st.dataframe(df_f.drop(columns=['en_dt']), use_container_width=True)

elif menu == "💸 Despesas":
    st.title("Despesas")
    seletor_periodo()
    df_d = get_data(ws_des)
    df_d['dt_dt'] = pd.to_datetime(df_d['data'])
    df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()

    t1, t2, t3 = st.tabs(["➕ Nova", "✏️ Editar", "🗑️ Apagar"])
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
            id_e_d = st.selectbox("ID para Editar", df_fd['id'].tolist())
            des_data = df_fd[df_fd['id'] == id_e_d].iloc[0]
            with st.form("edit_d_form"):
                dt_e = st.date_input("Data", value=pd.to_datetime(des_data['data']))
                ds_e = st.text_input("Descrição", value=des_data['descricao'])
                vl_e = st.number_input("Valor", value=float(des_data['valor']))
                if st.form_submit_button("Atualizar"):
                    ws_des.update(f'A{df_d[df_d["id"]==id_e_d].index[0]+2}:D{df_d[df_d["id"]==id_e_d].index[0]+2}', [[int(id_e_d), str(dt_e), ds_e, vl_e]])
                    st.rerun()

    with t3:
        if not df_fd.empty:
            id_d_d = st.selectbox("ID para Apagar", df_fd['id'].tolist())
            if st.button("CONFIRMAR EXCLUSÃO"):
                delete_by_id(ws_des, id_d_d); st.rerun()

    st.dataframe(df_fd.drop(columns=['dt_dt']), use_container_width=True)

elif menu == "📅 Calendário":
    st.title("Calendário")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
