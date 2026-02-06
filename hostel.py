import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime, date
from streamlit_calendar import calendar

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro | Elite", layout="wide", page_icon="🏨")

# --- 2. CONEXÃO COM CACHE (PARA EVITAR ERRO 429) ---
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
        st.error(f"Erro de credenciais: {e}")
        return None

client = init_connection()

# FUNÇÃO PARA LER DADOS COM CACHE DE 5 MINUTOS
@st.cache_data(ttl=300)
def fetch_sheet_data(sheet_name):
    try:
        spreadsheet = client.open("hostel-db")
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        # Normaliza colunas
        df.columns = df.columns.str.strip().str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        return df
    except Exception as e:
        st.error(f"Erro ao ler aba {sheet_name}: {e}")
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

# --- 4. FUNÇÕES DE ESCRITA (LIMPAM O CACHE APÓS ALTERAR) ---
def save_entry(sheet_name, row_data, row_id=None):
    try:
        spreadsheet = client.open("hostel-db")
        ws = spreadsheet.worksheet(sheet_name)
        if row_id: # Editar
            data = ws.get_all_records()
            for i, row in enumerate(data):
                if str(row.get('id')) == str(row_id):
                    # Define o range conforme a aba (Reservas J, Despesas D)
                    end_col = "J" if sheet_name == "reservas" else "D"
                    ws.update(f'A{i+2}:{end_col}{i+2}', [row_data])
                    break
        else: # Novo
            ws.append_row(row_data)
        
        # LIMPA O CACHE para forçar a leitura dos novos dados
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def delete_entry(sheet_name, row_id):
    try:
        spreadsheet = client.open("hostel-db")
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_records()
        for i, row in enumerate(data):
            if str(row.get('id')) == str(row_id):
                ws.delete_rows(i + 2)
                break
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return False

# --- 5. LÓGICA DE TAXAS (MANTIDA CONFORME ÚLTIMA ORDEM) ---
def calcular_taxa_reserva(row):
    total = float(row.get('total', 0))
    origem = str(row.get('origem', '')).strip()
    forma = str(row.get('forma_pgto', '')).strip()
    taxa_origem = 0.13 if origem == "Booking" else 0.0
    taxas_financeiras = {"Credito": 0.05, "Debito": 0.0239, "PIX": 0.0, "Dinheiro": 0.0}
    taxa_pgto = taxas_financeiras.get(forma, 0.0)
    return total * (taxa_origem + taxa_pgto)

# --- 6. NAVEGAÇÃO E UI ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

with st.sidebar:
    st.markdown("## HOSTEL PRO")
    menu = st.radio("MENU", ["💰 Dashboard", "📅 Calendário", "📋 Reservas", "💸 Despesas"])
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
    if st.button("Sair"):
        st.session_state["password_correct"] = False
        st.rerun()

m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
seletor_periodo = lambda: None # (Sua função de seletor aqui...)

# --- 7. MÓDULO DASHBOARD ---
if menu == "💰 Dashboard":
    st.title("BI Dashboard")
    df_r = fetch_sheet_data("reservas")
    df_d = fetch_sheet_data("despesas")
    
    # ... (Resto da lógica de cálculo de Bruto/Líquido usando df_r e df_d)
    # Use as colunas 'en_dt' e 'dt_dt' criando-as no momento do cálculo:
    if not df_r.empty:
        df_r['en_dt'] = pd.to_datetime(df_r['entrada'])
        # (Filtros e métricas aqui...)

# --- 8. MÓDULO RESERVAS ---
elif menu == "📋 Reservas":
    st.title("Gestão de Reservas")
    df_r = fetch_sheet_data("reservas")
    # ... (Lógica do formulário e listagem aqui)
    # Ao salvar, use: save_entry("reservas", new_row, id_se_for_edicao)
    # Ao deletar, use: delete_entry("reservas", row_id)
