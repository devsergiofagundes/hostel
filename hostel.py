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
        st.error(f"Erro na configuração: {e}")
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

# --- FUNÇÃO POP-UP (DIALOG) ---
@st.dialog("Detalhes da Reserva")
def detalhes_reserva(event_info):
    st.markdown(f"### {event_info['title']}")
    st.divider()
    
    c1, c2 = st.columns(2)
    c1.metric("Check-in", event_info['start'])
    c2.metric("Check-out", event_info['end'])
    
    if "extendedProps" in event_info:
        props = event_info["extendedProps"]
        st.write(f"**👤 Hóspedes:** {props.get('hospedes')}")
        st.write(f"**💰 Total:** R$ {props.get('total', 0):,.2f}")
    
    st.divider()
    # O botão agora apenas fecha o dialog nativamente. 
    # O segredo para não reabrir está na lógica da Agenda abaixo.
    if st.button("Fechar", use_container_width=True):
        st.rerun()

# --- NAVEGAÇÃO ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

if menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    df_res = get_data(ws_reservas)
    
    if not df_res.empty:
        calendar_events = []
        for _, row in df_res.iterrows():
            color = "#3D5AFE" if row['quarto'] == "Master" else "#00C853" if row['quarto'] == "Studio" else "#FF6D00"
            calendar_events.append({
                "title": f"{row['quarto']} - {row['nome']}",
                "start": str(row['entrada']),
                "end": str(row['saida']),
                "color": color,
                "extendedProps": {"hospedes": row['hospedes'], "total": row['total']}
            })

        calendar_options = {
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek"},
            "initialView": "dayGridMonth",
            "locale": "pt-br",
            "selectable": True,
        }

        # Renderização do calendário
        # Importante: A key deve ser fixa para não perder a referência
        state = calendar(events=calendar_events, options=calendar_options, key='hostel_calendar')
        
        # LÓGICA DE DETECÇÃO DE CLIQUE:
        # Verificamos se há um clique e se ele é "novo" usando session_state
        if state.get("eventClick"):
            event_id = state["eventClick"]["event"]["title"] + state["eventClick"]["event"]["start"]
            
            if "last_event_id" not in st.session_state or st.session_state.last_event_id != event_id:
                st.session_state.last_event_id = event_id
                detalhes_reserva(state["eventClick"]["event"])
        else:
            # Se não houver clique ativo, limpamos o ID para permitir clicar na mesma reserva de novo depois
            if "last_event_id" in st.session_state:
                st.session_state.last_event_id = None

        st.info("🔵 Master | 🟢 Studio | 🟠 Triplo")
    else:
        st.info("Sem reservas.")

# --- MÓDULOS RESTANTES (RESERVAS/DESPESAS/FINANCEIRO) ---
elif menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome")
            hospedes = st.number_input("Hóspedes", 1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            entrada = st.date_input("Entrada")
            saida = st.date_input("Saída")
            total = st.number_input("Total", 0.0)
            if st.form_submit_button("Salvar"):
                if (saida - entrada).days > 0:
                    ws_reservas.append_row([int(datetime.now().timestamp()), nome, hospedes, quarto, str(entrada), str(saida), (saida-entrada).days, total])
                    st.success("Salvo!")
                    st.rerun()
    with col2:
        df_res = get_data(ws_reservas)
        if not df_res.empty:
            st.dataframe(df_res)

elif menu == "Despesas":
    st.header("💸 Despesas")
    df_d = get_data(ws_despesas)
    st.dataframe(df_d)

elif menu == "Financeiro":
    st.header("💰 Financeiro")
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    r = df_res['total'].sum() if not df_res.empty else 0
    g = df_desp['valor'].sum() if not df_desp.empty else 0
    st.metric("Lucro", f"R$ {r-g:,.2f}")
