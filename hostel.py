import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro Cloud", layout="wide", page_icon="🏨")

# --- CONEXÃO SEGURA COM GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    try:
        # Puxa o conteúdo do JSON que colaste nos Secrets
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds_dict = json.loads(json_info)
        
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro na configuração das credenciais: {e}")
        return None

client = init_connection()

if client:
    try:
        # SUBSTITUA PELO NOME DA SUA PLANILHA NO GOOGLE DRIVE
        spreadsheet = client.open("NOME_DA_SUA_PLANILHA")
        ws_reservas = spreadsheet.worksheet("reservas")
        ws_despesas = spreadsheet.worksheet("despesas")
    except Exception as e:
        st.error(f"Erro ao abrir a planilha: {e}")
        st.info("Dica: Partilhe a planilha com o e-mail do Service Account que está no seu JSON.")
        st.stop()
else:
    st.stop()

# --- NAVEGAÇÃO ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- FUNÇÃO PARA OBTER DADOS ---
def get_data(worksheet):
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# --- MÓDULO DE RESERVAS ---
if menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Nova Reserva")
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            quarto = st.selectbox("Quarto", ["Dormitório A", "Dormitório B", "Suite 1", "Suite 2"])
            checkin = st.date_input("Check-in")
            checkout = st.date_input("Check-out")
            valor = st.number_input("Valor Total (R$)", min_value=0.0)
            
            if st.form_submit_button("Guardar Reserva"):
                novo_id = int(datetime.now().timestamp())
                ws_reservas.append_row([novo_id, nome, quarto, str(checkin), str(checkout), valor])
                st.success("Reserva guardada com sucesso!")
                st.rerun()

    with col2:
        st.subheader("Lista de Reservas")
        df_res = get_data(ws_reservas)
        if not df_res.empty:
            st.dataframe(df_res, use_container_width=True)
            
            res_id_excluir = st.selectbox("Selecionar ID para apagar", df_res['id'].tolist())
            if st.button("🗑️ Apagar Reserva"):
                cell = ws_reservas.find(str(res_id_excluir))
                ws_reservas.delete_rows(cell.row)
                st.warning("Reserva eliminada.")
                st.rerun()

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Painel Financeiro")
    
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    
    faturamento = df_res['valor'].sum() if not df_res.empty else 0.0
    gastos = df_desp['valor'].sum() if not df_desp.empty else 0.0
    saldo = faturamento - gastos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento", f"R$ {faturamento:,.2f}")
    c2.metric("Despesas", f"R$ {gastos:,.2f}", delta_color="inverse")
    c3.metric("Lucro Líquido", f"R$ {saldo:,.2f}")

# --- MÓDULO AGENDA ---
elif menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        # Visualização simples em tabela ordenada por data
        df_sorted = df_res.sort_values(by="checkin")
        st.table(df_sorted[['checkin', 'checkout', 'nome', 'quarto']])
    else:
        st.info("Sem reservas registadas.")
