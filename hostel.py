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
        spreadsheet = client.open("hostel-db")
        ws_reservas = spreadsheet.worksheet("reservas")
        ws_despesas = spreadsheet.worksheet("despesas")
    except Exception as e:
        st.error(f"Erro ao abrir a planilha: {e}")
        st.stop()
else:
    st.stop()

# --- FUNÇÃO PARA OBTER DADOS ---
def get_data(worksheet):
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# --- NAVEGAÇÃO ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- MÓDULO DE RESERVAS ---
if menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Nova Reserva")
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            qtd_hospedes = st.number_input("Quantidade de Hóspedes", min_value=1, step=1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            entrada = st.date_input("Data de Entrada (Check-in)")
            saida = st.date_input("Data de Saída (Check-out)")
            total_valor = st.number_input("Valor Total (R$)", min_value=0.0)
            
            if st.form_submit_button("Guardar Reserva"):
                # Cálculo automático de diárias
                delta = saida - entrada
                n_diarias = delta.days
                
                if n_diarias <= 0:
                    st.error("Erro: A data de saída deve ser posterior à entrada.")
                else:
                    novo_id = int(datetime.now().timestamp())
                    # ORDEM: id, nome, hospedes, quarto, entrada, saida, diarias, total
                    nova_linha = [
                        novo_id, 
                        nome, 
                        qtd_hospedes, 
                        quarto, 
                        str(entrada), 
                        str(saida), 
                        n_diarias, 
                        total_valor
                    ]
                    ws_reservas.append_row(nova_linha)
                    st.success(f"Reserva de {nome} guardada!")
                    st.rerun()

    with col2:
        st.subheader("Lista de Reservas")
        df_res = get_data(ws_reservas)
        if not df_res.empty:
            st.dataframe(df_res, use_container_width=True)
            
            # Deleção baseada no ID (evita KeyError)
            id_col = 'id' if 'id' in df_res.columns else df_res.columns[0]
            res_id_excluir = st.selectbox("Selecionar ID para apagar", df_res[id_col].tolist())
            
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
    
    # Ajustado para usar a coluna 'total' conforme sua planilha
    faturamento = df_res['total'].sum() if not df_res.empty else 0.0
    gastos = df_desp['valor'].sum() if not df_desp.empty else 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento", f"R$ {faturamento:,.2f}")
    c2.metric("Despesas", f"R$ {gastos:,.2f}", delta_color="inverse")
    c3.metric("Lucro Líquido", f"R$ {faturamento - gastos:,.2f}")

# --- MÓDULO AGENDA ---
elif menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        # Ordenar pela coluna 'entrada'
        df_sorted = df_res.sort_values(by="entrada")
        st.dataframe(df_sorted[['entrada', 'saida', 'nome', 'quarto', 'hospedes']], use_container_width=True)
    else:
        st.info("Sem reservas registadas.")

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Gestão de Despesas")
    with st.form("form_despesa", clear_on_submit=True):
        tipo = st.text_input("Descrição da Despesa")
        valor_d = st.number_input("Valor (R$)", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            ws_despesas.append_row([int(datetime.now().timestamp()), tipo, valor_d])
            st.success("Despesa anotada!")
            st.rerun()
