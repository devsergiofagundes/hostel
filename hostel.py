import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro Ultra Cloud", layout="wide", page_icon="🏨")

# --- CONEXÃO SEGURA COM GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    # Carrega as credenciais da aba 'Secrets' do Streamlit Cloud
    creds_info = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    return client

try:
    client = init_connection()
    # Substitua pelo nome exato da sua planilha no Google Drive
    sh = client.open("HostelData") 
    ws_res = sh.worksheet("reservas")
    ws_desp = sh.worksheet("despesas")
except Exception as e:
    st.error("Erro de conexão. Verifique se os Secrets foram configurados no Streamlit Cloud.")
    st.stop()

# --- ESTILIZAÇÃO CSS (Opcional, para manter o visual Dark) ---
st.markdown("""
    <style>
    .main { background-color: #0F172A; }
    .stMetric { background-color: #1E293B; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🏨 Hostel Pro Ultra")
menu = st.sidebar.radio("Navegação", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- MÓDULO DE RESERVAS ---
if menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Nova Reserva")
        with st.form("add_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            quarto = st.selectbox("Quarto", ["Dormitório A", "Dormitório B", "Privativo 1", "Privativo 2"])
            hospedes = st.number_input("Hóspedes", min_value=1, value=1)
            entrada = st.date_input("Check-in")
            saida = st.date_input("Check-out")
            total = st.number_input("Total R$", min_value=0.0)
            
            if st.form_submit_button("Confirmar Reserva"):
                id_res = int(datetime.now().timestamp())
                ws_res.append_row([id_res, nome, hospedes, str(entrada), str(saida), total, quarto])
                st.success("Salvo no Google Sheets!")
                st.rerun()

    with col2:
        st.subheader("Lista de Reservas")
        data = ws_res.get_all_records()
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df.sort_values(by="entrada", ascending=False), use_container_width=True)
            
            # Deletar
            res_id = st.selectbox("Excluir Reserva (ID)", df['id'].tolist())
            if st.button("🗑️ Remover permanentemente"):
                cell = ws_res.find(str(res_id))
                ws_res.delete_rows(cell.row)
                st.warning("Reserva excluída.")
                st.rerun()

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Financeiro")
    
    df_res = pd.DataFrame(ws_res.get_all_records())
    df_desp = pd.DataFrame(ws_desp.get_all_records())
    
    bruto = df_res['total'].sum() if not df_res.empty else 0
    gastos = df_desp['valor'].sum() if not df_desp.empty else 0
    
    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento Bruto", f"R$ {bruto:.2f}")
    c2.metric("Total Despesas", f"R$ {gastos:.2f}", delta_color="inverse")
    c3.metric("Lucro Líquido", f"R$ {bruto - gastos:.2f}")

    st.divider()
    st.subheader("Detalhamento de Gastos")
    if not df_desp.empty:
        st.table(df_desp)

# --- MÓDULO AGENDA ---
elif menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    # Lógica de calendário simplificada para visualização web
    df_res = pd.DataFrame(ws_res.get_all_records())
    if not df_res.empty:
        st.write("Reservas ativas no período:")
        st.dataframe(df_res[['nome', 'quarto', 'entrada', 'saida']])
    else:
        st.info("Nenhuma reserva para exibir.")
