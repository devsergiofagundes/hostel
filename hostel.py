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
            if 'origem' in df_mes_r.columns:
                # Booking: 18%
                tax_booking = df_mes_r[df_mes_r['origem'] == 'Booking']['total'].sum() * 0.18
                # Telefone e Whatsapp: Apenas 5%
                tax_direta = df_mes_r[df_mes_r['origem'].isin(['Telefone', 'Whatsapp'])]['total'].sum() * 0.05
                taxas = tax_booking + tax_direta
            else: 
                taxas = bruto * 0.18

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
        st.subheader("Ocupação por Quarto")
        if not df_mes_r.empty:
            df_plot = df_mes_r.copy()
            df_plot['quarto'] = df_plot['quarto'].astype(str).str.split(', ')
            st.bar_chart(df_plot.explode('quarto').groupby('quarto')['total'].count())
        else: st.info("Sem dados")
    with cg2:
        st.subheader("Divisão Financeira")
        if bruto > 0:
            st.bar_chart(pd.DataFrame({"Valor": [taxas, operacionais, liquido]}, index=["Taxas", "Operacional", "Lucro"]))

elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    seletor_periodo()
    df_r = get_data(ws_res)
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()
    else:
        df_f = pd.DataFrame()

    t1, t2, t3 = st.tabs(["➕ Nova", "✏️ Editar", "🗑️ Apagar"])
    
    with t1:
        with st.form("add_r"):
            nome = st.text_input("Nome do Hóspede")
            hospedes = st.number_input("Hóspedes", min_value=1, value=1)
            q_sel = st.multiselect("Quartos", ["Master", "Studio", "Triplo"], ["Master"])
            en, sa = st.columns(2)
            ent, sai = en.date_input("Check-in"), sa.date_input("Check-out")
            origem = st.selectbox("Origem", ["Booking", "Telefone", "Whatsapp"])
            val = st.number_input("Valor Total R$", 0.0)
            if st.form_submit_button("Salvar Reserva"):
                ws_res.append_row([
                    int(datetime.now().timestamp()), nome, hospedes, ", ".join(q_sel), 
                    str(ent), str(sai), (sai-ent).days, val, origem
                ])
                st.rerun()

    with t2:
        if not df_f.empty:
            id_edit = st.selectbox("Selecione ID para Editar", df_f['id'].tolist())
            res_data = df_f[df_f['id'] == id_edit].iloc[0]
            with st.form("edit_r_form"):
                nome_e = st.text_input("Nome", value=res_data['nome'])
                h_e = st.number_input("Hóspedes", min_value=1, value=int(res_data.get('hospedes', 1)))
                q_atual = str(res_data['quarto']).split(", ")
                q_e = st.multiselect("Quartos", ["Master", "Studio", "Triplo"], q_atual)
                en_e, sa_e = st.columns(2)
                ent_e = en_e.date_input("In", value=pd.to_datetime(res_data['entrada']))
                sai_e = sa_e.date_input("Out", value=pd.to_datetime(res_data['saida']))
                
                # Definir índice correto para o selectbox de origem
                lista_origens = ["Booking", "Telefone", "Whatsapp"]
                origem_atual = res_data.get('origem', "Booking")
                idx_origem = lista_origens.index(origem_atual) if origem_atual in lista_origens else 0
                
                origem_e = st.selectbox("Origem", lista_origens, index=idx_origem)
                val_e = st.number_input("Valor", value=float(res_data['total']))
                
                if st.form_submit_button("Atualizar Dados"):
                    new_row = [int(id_edit), nome_e, h_e, ", ".join(q_e), str(ent_e), str(sai_e), (sai_e-ent_e).days, val_e, origem_e]
                    update_row(ws_res, id_edit, new_row)
                    st.rerun()

    with t3:
        if not df_f.empty:
            id_del = st.selectbox("Selecione ID para Apagar", df_f['id'].tolist())
            if st.button("CONFIRMAR EXCLUSÃO"):
                delete_by_id(ws_res, id_del); st.rerun()

    if not df_f.empty:
        st.dataframe(df_f.drop(columns=['en_dt']), use_container_width=True, hide_index=True)

elif menu == "💸 Despesas":
    st.title("Gestão de Despesas")
    seletor_periodo()
    df_d = get_data(ws_des)
    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()
    else:
        df_fd = pd.DataFrame()

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
            id_e_d = st.selectbox("ID da Despesa", df_fd['id'].tolist())
            des_data = df_fd[df_fd['id'] == id_e_d].iloc[0]
            with st.form("edit_d_form"):
                dt_e = st.date_input("Data", value=pd.to_datetime(des_data['data']))
                ds_e = st.text_input("Descrição", value=des_data['descricao'])
                vl_e = st.number_input("Valor", value=float(des_data['valor']))
                if st.form_submit_button("Atualizar"):
                    row_idx = df_d[df_d["id"] == id_e_d].index[0] + 2
                    ws_des.update(f'A{row_idx}:D{row_idx}', [[int(id_e_d), str(dt_e), ds_e, vl_e]])
                    st.rerun()

    with t3:
        if not df_fd.empty:
            id_d_d = st.selectbox("Selecione ID para Apagar", df_fd['id'].tolist())
            if st.button("CONFIRMAR EXCLUSÃO"):
                delete_by_id(ws_des, id_d_d); st.rerun()

    if not df_fd.empty:
        st.dataframe(df_fd.drop(columns=['dt_dt']), use_container_width=True, hide_index=True)

elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
