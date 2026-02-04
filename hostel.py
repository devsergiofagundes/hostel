import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro Cloud", layout="wide", page_icon="🏨")

# --- CONEXÃO SEGURA ---
@st.cache_resource
def init_connection():
    try:
        json_info = st.secrets["gcp_service_account"]["json_content"]
        creds_dict = json.loads(json_info)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro: {e}")
        return None

client = init_connection()

if client:
    try:
        spreadsheet = client.open("hostel-db")
        ws_reservas = spreadsheet.worksheet("reservas")
        ws_despesas = spreadsheet.worksheet("despesas")
    except Exception as e:
        st.error(f"Erro ao abrir planilha: {e}")
        st.stop()
else:
    st.stop()

def get_data(worksheet):
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# --- NAVEGAÇÃO ---
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- MÓDULO DE RESERVAS ---
if menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Nova Reserva")
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            qtd_hospedes = st.number_input("Hóspedes", min_value=1, step=1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            entrada = st.date_input("Check-in")
            saida = st.date_input("Check-out")
            total_valor = st.number_input("Valor Total (R$)", min_value=0.0)
            
            if st.form_submit_button("Guardar Reserva"):
                n_diarias = (saida - entrada).days
                
                if n_diarias <= 0:
                    st.error("A data de saída deve ser após a entrada.")
                else:
                    novo_id = int(datetime.now().timestamp())
                    
                    # --- ORDEM CORRIGIDA PARA BATER COM SEU CABEÇALHO ---
                    # 1.id | 2.nome | 3.hospedes | 4.quarto | 5.entrada | 6.saida | 7.diarias | 8.total
                    nova_linha = [
                        novo_id,            # id
                        nome,               # nome
                        qtd_hospedes,       # hospedes
                        quarto,             # quarto
                        str(entrada),       # entrada
                        str(saida),         # saida
                        n_diarias,          # diarias
                        total_valor         # total
                    ]
                    
                    ws_reservas.append_row(nova_linha)
                    st.success(f"Reserva de {nome} salva com sucesso!")
                    st.rerun()

    with col2:
        st.subheader("Lista de Reservas")
        df_res = get_data(ws_reservas)
        if not df_res.empty:
            # Exibe o DataFrame para conferência
            st.dataframe(df_res, use_container_width=True)
            
            # Deleção
            lista_ids = df_res['id'].tolist() if 'id' in df_res.columns else []
            if lista_ids:
                res_id_excluir = st.selectbox("Selecionar ID para apagar", lista_ids)
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
    
    faturamento = df_res['total'].sum() if not df_res.empty and 'total' in df_res.columns else 0.0
    gastos = df_desp['valor'].sum() if not df_desp.empty and 'valor' in df_desp.columns else 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento", f"R$ {faturamento:,.2f}")
    c2.metric("Despesas", f"R$ {gastos:,.2f}")
    c3.metric("Lucro Líquido", f"R$ {faturamento - gastos:,.2f}")

# --- MÓDULO AGENDA ---
elif menu == "Agenda":
    st.header("📅 Agenda")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        # Mostra colunas específicas para facilitar a leitura da agenda
        st.dataframe(df_res[['entrada', 'saida', 'quarto', 'nome']], use_container_width=True)
    else:
        st.info("Nenhuma reserva.")

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Despesas")
    with st.form("form_despesa", clear_on_submit=True):
        desc = st.text_input("Descrição")
        valor_d = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            # id, tipo, valor
            ws_despesas.append_row([int(datetime.now().timestamp()), desc, valor_d])
            st.rerun()
