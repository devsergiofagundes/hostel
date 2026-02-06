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
                tax_booking = df_mes_r[df_mes_r['origem'] == 'Booking']['total'].sum() * 0.18
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
    c1.metric("BRUTO TOTAL", f"R$ {bruto:,.2f}")
    c2.metric("TAXAS TOTAIS", f"R$ {taxas:,.2f}")
    c3.metric("DESPESAS TOTAIS", f"R$ {operacionais:,.2f}")
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

    st.markdown("---")
    st.subheader(f"Resumo Financeiro Realizado (01/{m:02d} até {date.today().strftime('%d/%m/%Y')})")
    
    bruto_hoje, taxas_hoje, operacionais_hoje = 0.0, 0.0, 0.0
    hoje = date.today()

    if not df_mes_r.empty:
        df_hoje_r = df_mes_r[df_mes_r['en_dt'].dt.date <= hoje]
        if not df_hoje_r.empty:
            bruto_hoje = df_hoje_r['total'].sum()
            if 'origem' in df_hoje_r.columns:
                tax_b_h = df_hoje_r[df_hoje_r['origem'] == 'Booking']['total'].sum() * 0.18
                tax_d_h = df_hoje_r[df_hoje_r['origem'].isin(['Telefone', 'Whatsapp'])]['total'].sum() * 0.05
                taxas_hoje = tax_b_h + tax_d_h
            else:
                taxas_hoje = bruto_hoje * 0.18

    if not df_d.empty:
        df_hoje_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a) & (df_d['dt_dt'].dt.date <= hoje)]
        operacionais_hoje = df_hoje_d['valor'].sum()

    liquido_hoje = bruto_hoje - taxas_hoje - operacionais_hoje

    ch1, ch2, ch3, ch4 = st.columns(4)
    ch1.metric("BRUTO ATÉ HOJE", f"R$ {bruto_hoje:,.2f}")
    ch2.metric("TAXAS ATÉ HOJE", f"R$ {taxas_hoje:,.2f}")
    ch3.metric("DESPESAS ATÉ HOJE", f"R$ {operacionais_hoje:,.2f}")
    ch4.metric("LUCRO ATÉ HOJE", f"R$ {liquido_hoje:,.2f}")

elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    seletor_periodo()
    
    if st.button("➕ Nova Reserva"):
        st.session_state.edit_mode = "novo"
        st.session_state.item_selecionado = None

    df_r = get_data(ws_res)
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy()
        df_f = df_f.sort_values(by='en_dt', ascending=False)
        
        st.markdown("### Listagem de Reservas")
        # Header da tabela customizada
        h_cols = st.columns([1, 3, 2, 2, 2, 1, 1])
        h_cols[0].write("**ID**")
        h_cols[1].write("**Nome**")
        h_cols[2].write("**Entrada**")
        h_cols[3].write("**Quarto**")
        h_cols[4].write("**Total**")
        h_cols[5].write("**✏️**")
        h_cols[6].write("**🗑️**")
        st.divider()

        for idx, row in df_f.iterrows():
            cols = st.columns([1, 3, 2, 2, 2, 1, 1])
            cols[0].write(f"`{row['id']}`")
            cols[1].write(row['nome'])
            cols[2].write(pd.to_datetime(row['entrada']).strftime('%d/%m/%Y'))
            cols[3].write(row['quarto'])
            cols[4].write(f"R$ {row['total']:,.2f}")
            
            if cols[5].button("📝", key=f"ed_{row['id']}"):
                st.session_state.edit_mode = "editar"
                st.session_state.item_selecionado = row
            
            if cols[6].button("🗑️", key=f"del_{row['id']}"):
                delete_by_id(ws_res, row['id'])
                st.rerun()

    # Modal de Edição/Criação simulado
    if "edit_mode" in st.session_state and st.session_state.edit_mode:
        with st.sidebar.expander("FORMULÁRIO DE RESERVA", expanded=True):
            mode = st.session_state.edit_mode
            data = st.session_state.item_selecionado
            
            with st.form("form_r"):
                st.subheader("Editar" if mode == "editar" else "Nova Reserva")
                nome_f = st.text_input("Nome", value=data['nome'] if data is not None else "")
                hosp_f = st.number_input("Hóspedes", min_value=1, value=int(data['hospedes']) if data is not None else 1)
                q_atual = str(data['quarto']).split(", ") if data is not None else ["Master"]
                q_f = st.multiselect("Quartos", ["Master", "Studio", "Triplo"], q_atual)
                ent_f = st.date_input("In", value=pd.to_datetime(data['entrada']) if data is not None else date.today())
                sai_f = st.date_input("Out", value=pd.to_datetime(data['saida']) if data is not None else date.today())
                val_f = st.number_input("Valor", value=float(data['total']) if data is not None else 0.0)
                orig_f = st.selectbox("Origem", ["Booking", "Telefone", "Whatsapp"], index=0)

                if st.form_submit_button("SALVAR"):
                    new_data = [int(data['id']) if mode == "editar" else int(datetime.now().timestamp()), 
                                nome_f, hosp_f, ", ".join(q_f), str(ent_f), str(sai_f), (sai_f-ent_f).days, val_f, orig_f]
                    if mode == "editar":
                        update_row(ws_res, data['id'], new_data)
                    else:
                        ws_res.append_row(new_data)
                    st.session_state.edit_mode = None
                    st.rerun()
                if st.form_submit_button("CANCELAR"):
                    st.session_state.edit_mode = None
                    st.rerun()

elif menu == "💸 Despesas":
    st.title("Gestão de Despesas")
    seletor_periodo()
    
    if st.button("➕ Nova Despesa"):
        st.session_state.edit_mode_d = "novo"
        st.session_state.item_selecionado_d = None

    df_d = get_data(ws_des)
    if not df_d.empty:
        df_d['dt_dt'] = pd.to_datetime(df_d['data'])
        df_fd = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)].copy()
        df_fd = df_fd.sort_values(by='dt_dt', ascending=False)

        st.markdown("### Listagem de Despesas")
        h_cols = st.columns([1, 2, 4, 2, 1, 1])
        h_cols[0].write("**ID**")
        h_cols[1].write("**Data**")
        h_cols[2].write("**Descrição**")
        h_cols[3].write("**Valor**")
        h_cols[4].write("**✏️**")
        h_cols[5].write("**🗑️**")
        st.divider()

        for idx, row in df_fd.iterrows():
            cols = st.columns([1, 2, 4, 2, 1, 1])
            cols[0].write(f"`{row['id']}`")
            cols[1].write(pd.to_datetime(row['data']).strftime('%d/%m/%Y'))
            cols[2].write(row['descricao'])
            cols[3].write(f"R$ {row['valor']:,.2f}")
            
            if cols[4].button("📝", key=f"ed_d_{row['id']}"):
                st.session_state.edit_mode_d = "editar"
                st.session_state.item_selecionado_d = row
            
            if cols[5].button("🗑️", key=f"del_d_{row['id']}"):
                delete_by_id(ws_des, row['id'])
                st.rerun()

    if "edit_mode_d" in st.session_state and st.session_state.edit_mode_d:
        with st.sidebar.expander("FORMULÁRIO DE DESPESA", expanded=True):
            mode = st.session_state.edit_mode_d
            data = st.session_state.item_selecionado_d
            with st.form("form_d"):
                dt_f = st.date_input("Data", value=pd.to_datetime(data['data']) if data is not None else date.today())
                desc_f = st.text_input("Descrição", value=data['descricao'] if data is not None else "")
                val_f = st.number_input("Valor", value=float(data['valor']) if data is not None else 0.0)
                
                if st.form_submit_button("SALVAR"):
                    row_id = data['id'] if mode == "editar" else int(datetime.now().timestamp())
                    new_row = [row_id, str(dt_f), desc_f, val_f]
                    if mode == "editar":
                        # Busca o índice real na planilha via ID
                        r_idx = df_d[df_d["id"] == row_id].index[0] + 2
                        ws_des.update(f'A{r_idx}:D{r_idx}', [new_row])
                    else:
                        ws_des.append_row(new_row)
                    st.session_state.edit_mode_d = None
                    st.rerun()
                if st.form_submit_button("CANCELAR"):
                    st.session_state.edit_mode_d = None
                    st.rerun()

elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data(ws_res)
    if not df.empty:
        evs = [{"title": f"{r['quarto']} | {r['nome']}", "start": str(r['entrada']), "end": str(r['saida']), "color": "#4318FF"} for _, r in df.iterrows()]
        calendar(events=evs)
