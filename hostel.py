import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

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

# --- FUNÇÃO POP-UP (DIALOG) ---
@st.dialog("Detalhes da Reserva")
def detalhes_reserva(event_info):
    # O event_info traz os dados do dicionário 'calendar_events'
    st.write(f"### {event_info['title']}")
    st.write("---")
    st.write(f"**📅 Início:** {event_info['start']}")
    st.write(f"**🏁 Fim:** {event_info['end']}")
    
    # Se quiser exibir mais dados que não estão no título, 
    # você pode passar metadados extras no dicionário do evento.
    if "extendedProps" in event_info:
        props = event_info["extendedProps"]
        st.write(f"**👤 Hóspedes:** {props.get('hospedes', 'N/A')}")
        st.write(f"**💰 Valor Total:** R$ {props.get('total', 0):,.2f}")
    
    if st.button("Fechar"):
        st.rerun()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- MÓDULO AGENDA (CALENDÁRIO) ---
if menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    df_res = get_data(ws_reservas)
    
    if not df_res.empty:
        calendar_events = []
        for _, row in df_res.iterrows():
            color = "#3D5AFE"  # Master
            if row['quarto'] == "Studio": color = "#00C853"
            if row['quarto'] == "Triplo": color = "#FF6D00"

            calendar_events.append({
                "title": f"{row['quarto']} - {row['nome']}",
                "start": str(row['entrada']),
                "end": str(row['saida']),
                "color": color,
                # Passamos dados extras para o Pop-up aqui:
                "extendedProps": {
                    "hospedes": row['hospedes'],
                    "total": row['total']
                }
            })

        calendar_options = {
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,dayGridWeek",
            },
            "initialView": "dayGridMonth",
            "locale": "pt-br",
            "selectable": True,
        }

        # Captura o clique no calendário
        state = calendar(events=calendar_events, options=calendar_options, key='hostel_calendar')
        
        # Se um evento for clicado, abre o Pop-up
        if state.get("eventClick"):
            detalhes_reserva(state["eventClick"]["event"])

        st.info("🔵 Master | 🟢 Studio | 🟠 Triplo")
    else:
        st.info("Sem reservas registradas.")

# --- MÓDULO RESERVAS ---
elif menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Nova Reserva")
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            hospedes = st.number_input("Hóspedes", min_value=1, step=1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            entrada = st.date_input("Entrada")
            saida = st.date_input("Saída")
            total = st.number_input("Total (R$)", min_value=0.0)
            
            if st.form_submit_button("Salvar"):
                diarias = (saida - entrada).days
                if diarias > 0:
                    novo_id = int(datetime.now().timestamp())
                    ws_reservas.append_row([novo_id, nome, hospedes, quarto, str(entrada), str(saida), diarias, total])
                    st.success("Reserva salva!")
                    st.rerun()
                else:
                    st.error("Data de saída inválida.")

    with col2:
        df_res = get_data(ws_reservas)
        if not df_res.empty:
            st.dataframe(df_res, use_container_width=True)
            id_del = st.selectbox("ID para apagar", df_res['id'].tolist())
            if st.button("🗑️ Apagar"):
                cell = ws_reservas.find(str(id_del))
                ws_reservas.delete_rows(cell.row)
                st.rerun()

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Despesas")
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("form_desp"):
            data_d = st.date_input("Data")
            desc = st.text_input("Descrição")
            valor = st.number_input("Valor", min_value=0.0)
            if st.form_submit_button("Salvar"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(data_d), desc, valor])
                st.rerun()
    with c2:
        df_d = get_data(ws_despesas)
        if not df_d.empty:
            st.dataframe(df_d, use_container_width=True)

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Financeiro")
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    
    receita = df_res['total'].sum() if not df_res.empty else 0.0
    gastos = df_desp['valor'].sum() if not df_desp.empty else 0.0
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Faturamento", f"R$ {receita:,.2f}")
    col_b.metric("Despesas", f"R$ {gastos:,.2f}", delta_color="inverse")
    col_c.metric("Lucro Líquido", f"R$ {receita - gastos:,.2f}")
