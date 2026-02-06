import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- 2. CONEXÃO E CACHE ---
@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds = Credentials.from_service_account_info(
            json.loads(json_info), 
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

client = init_connection()

@st.cache_data(ttl=300) # Dados cacheados por 5 minutos
def get_data(sheet_name):
    try:
        spreadsheet = client.open("hostel-db")
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        return df
    except Exception as e:
        st.error(f"Erro ao ler {sheet_name}: {e}")
        return pd.DataFrame()

# --- 3. LOGIN ---
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

# --- 4. FUNÇÕES DE CÁLCULO E PERSISTÊNCIA ---
def calcular_taxa_reserva(row):
    total = float(row.get('total', 0))
    origem = str(row.get('origem', '')).strip()
    forma = str(row.get('forma_pgto', '')).strip()
    taxa_origem = 0.13 if origem == "Booking" else 0.0
    taxas_financeiras = {"Credito": 0.05, "Debito": 0.0239, "PIX": 0.0, "Dinheiro": 0.0}
    taxa_pgto = taxas_financeiras.get(forma, 0.0)
    return total * (taxa_origem + taxa_pgto)

def delete_by_id(sheet_name, row_id):
    ws = client.open("hostel-db").worksheet(sheet_name)
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row.get('id')) == str(row_id):
            ws.delete_rows(i + 2)
            st.cache_data.clear() # Limpa cache para atualizar lista
            return True
    return False

def update_or_add_row(sheet_name, row_data, row_id=None):
    ws = client.open("hostel-db").worksheet(sheet_name)
    if row_id: # Update
        data = ws.get_all_records()
        for i, row in enumerate(data):
            if str(row.get('id')) == str(row_id):
                # Determina coluna final (J para reservas, D para despesas)
                col_final = "J" if sheet_name == "reservas" else "D"
                ws.update(f'A{i+2}:{col_final}{i+2}', [row_data])
                break
    else: # Add
        ws.append_row(row_data)
    st.cache_data.clear() # Limpa cache após salvar

# --- 5. NAVEGAÇÃO ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

with st.sidebar:
    st.markdown("## HOSTEL PRO")
    menu = st.radio("MENU", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    if st.button("🔄 Sincronizar Agora"):
        st.cache_data.clear()
        st.rerun()
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

# --- 6. MÓDULOS ---

if menu == "💰 Dashboard":
    st.title("BI Dashboard")
    seletor_periodo()
    df_r = get_data("reservas")
    df_d = get_data("despesas")
    bruto, taxas, operacionais = 0.0, 0.0, 0.0
    
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_mes_r = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)]
        if not df_mes_r.empty:
            bruto = df_mes_r['total'].sum()
            taxas = df_mes_r.apply(calcular_taxa_reserva, axis=1).sum()

            liquido = bruto - taxas 
            if not df_d.empty:
                df_d['dt_dt'] = pd.to_datetime(df_d['data'])
                df_mes_d = df_d[(df_d['dt_dt'].dt.month == m) & (df_d['dt_dt'].dt.year == a)]
                operacionais = df_mes_d['valor'].sum()
                liquido -= operacionais

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PROJEÇÃO BRUTO", f"R$ {bruto:,.2f}")
            c2.metric("PROJEÇÃO TAXAS", f"R$ {taxas:,.2f}")
            c3.metric("PROJEÇÃO DESPESAS", f"R$ {operacionais:,.2f}")
            c4.metric("PROJEÇÃO LUCRO", f"R$ {bruto - taxas - operacionais:,.2f}")

elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    seletor_periodo()
    
    if "edit_mode" in st.session_state and st.session_state.edit_mode:
        with st.container(border=True):
            mode, data = st.session_state.edit_mode, st.session_state.item_selecionado
            with st.form("form_r"):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1.5])
                nome = c1.text_input("Nome", value=data['nome'] if data is not None else "")
                hosp = c2.number_input("Hóspedes", min_value=1, value=int(data['hospedes']) if data is not None else 1)
                orig = c3.selectbox("Origem", ["Booking", "Telefone", "Whatsapp"], index=0)
                lista_pgto = ["PIX", "Dinheiro", "Credito", "Debito"]
                idx_pgto = lista_pgto.index(data['forma_pgto']) if data is not None and data.get('forma_pgto') in lista_pgto else 0
                pgto = c4.selectbox("Pagamento", lista_pgto, index=idx_pgto)
                
                c5, c6, c7, c8 = st.columns(4)
                quartos = c5.multiselect("Quartos", ["Master", "Studio", "Triplo"], default=str(data['quarto']).split(", ") if data else ["Master"])
                ent = c6.date_input("Check-in", value=pd.to_datetime(data['entrada']) if data is not None else date.today())
                sai = c7.date_input("Check-out", value=pd.to_datetime(data['saida']) if data is not None else date.today())
                val = c8.number_input("Total R$", value=float(data['total']) if data is not None else 0.0)
                
                if st.form_submit_button("✅ SALVAR"):
                    rid = data['id'] if mode=="editar" else int(datetime.now().timestamp())
                    new = [rid, nome, hosp, ", ".join(quartos), str(ent), str(sai), (sai-ent).days, val, orig, pgto]
                    update_or_add_row("reservas", new, rid if mode=="editar" else None)
                    st.session_state.edit_mode = None
                    st.rerun()
                if st.form_submit_button("❌ CANCELAR"): st.session_state.edit_mode = None; st.rerun()

    if not st.session_state.get("edit_mode"):
        if st.button("➕ Nova Reserva"): 
            st.session_state.edit_mode = "novo"; st.session_state.item_selecionado = None; st.rerun()

    df_r = get_data("reservas")
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        df_f = df_r[(df_r['en_dt'].dt.month == m) & (df_r['en_dt'].dt.year == a)].copy().sort_values(by='en_dt', ascending=False)
        st.divider()
        for _, row in df_f.iterrows():
            cols = st.columns([0.6, 2.5, 1.5, 1.5, 1.5, 1.2, 0.6, 0.6])
            cols[1].write(row['nome'])
            cols[2].write(pd.to_datetime(row['entrada']).strftime('%d/%m'))
            cols[4].write(f"R$ {row['total']}")
            if cols[6].button("📝", key=f"e_{row['id']}"):
                st.session_state.edit_mode = "editar"; st.session_state.item_selecionado = row; st.rerun()
            if cols[7].button("🗑️", key=f"d_{row['id']}"): delete_by_id("reservas", row['id']); st.rerun()

elif menu == "💸 Despesas":
    st.title("Gestão de Despesas")
    seletor_periodo()
    if "edit_mode_d" in st.session_state and st.session_state.edit_mode_d:
        with st.form("form_d"):
            data_d = st.session_state.item_selecionado_d
            dt_p = st.date_input("Data", value=pd.to_datetime(data_d['data']) if data_d else date.today())
            ds_p = st.text_input("Descrição", value=data_d['descricao'] if data_d else "")
            vl_p = st.number_input("Valor", value=float(data_d['valor']) if data_d else 0.0)
            if st.form_submit_button("✅ SALVAR"):
                did = data_d['id'] if st.session_state.edit_mode_d == "editar" else int(datetime.now().timestamp())
                update_or_add_row("despesas", [did, str(dt_p), ds_p, vl_p], did if st.session_state.edit_mode_d == "editar" else None)
                st.session_state.edit_mode_d = None; st.rerun()

    df_d = get_data("despesas")
    if not df_d.empty:
        # Listagem de despesas similar às reservas...
        st.write(df_d) # Versão simplificada para poupar espaço

elif menu == "📅 Calendário":
    st.title("Mapa de Ocupação")
    df = get_data("reservas")
    if not df.empty:
        evs = [{"title": f"{r['nome']}", "start": str(r['entrada']), "end": str(r['saida'])} for _, r in df.iterrows()]
        calendar(events=evs)
