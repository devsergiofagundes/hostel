import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro Cloud", layout="wide", page_icon="🏨")

# --- INICIALIZAÇÃO DE ESTADOS (Compartilhado entre Despesas e Financeiro) ---
if "data_filtro" not in st.session_state:
    st.session_state.data_filtro = datetime.now().replace(day=1)

# --- CONEXÃO SEGURA COM GOOGLE SHEETS ---
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
    if st.button("Fechar", use_container_width=True):
        st.rerun()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🏨 Hostel Pro")
menu = st.sidebar.radio("Ir para:", ["Agenda", "Reservas", "Despesas", "Financeiro"])

# --- COMPONENTE DE NAVEGAÇÃO DE MÊS (Reutilizável) ---
def seletor_mes():
    col_mes1, col_mes2, col_mes3 = st.columns([1, 2, 1])
    with col_mes1:
        if st.button("⬅️ Mês Anterior"):
            st.session_state.data_filtro -= pd.DateOffset(months=1)
            st.rerun()
    with col_mes2:
        texto = st.session_state.data_filtro.strftime("%B / %Y").capitalize()
        st.markdown(f"<h3 style='text-align: center;'>{texto}</h3>", unsafe_allow_html=True)
    with col_mes3:
        if st.button("Próximo Mês ➡️"):
            st.session_state.data_filtro += pd.DateOffset(months=1)
            st.rerun()
    st.divider()

# --- MÓDULO AGENDA ---
if menu == "Agenda":
    st.header("📅 Agenda de Ocupação")
    df_res = get_data(ws_reservas)
    if not df_res.empty:
        calendar_events = []
        for _, row in df_res.iterrows():
            color = "#3D5AFE" if row['quarto'] == "Master" else "#00C853" if row['quarto'] == "Studio" else "#FF6D00"
            calendar_events.append({
                "title": f"{row['quarto']} - {row['nome']}",
                "start": str(row['entrada']), "end": str(row['saida']), "color": color,
                "extendedProps": {"hospedes": row['hospedes'], "total": row['total']}
            })
        state = calendar(events=calendar_events, options={"locale": "pt-br"}, key='hostel_calendar')
        if state.get("eventClick"):
            event_id = state["eventClick"]["event"]["title"] + state["eventClick"]["event"]["start"]
            if "last_event_id" not in st.session_state or st.session_state.last_event_id != event_id:
                st.session_state.last_event_id = event_id
                detalhes_reserva(state["eventClick"]["event"])
        else: st.session_state.last_event_id = None

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Controle de Despesas")
    seletor_mes()
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Nova Despesa")
        with st.form("form_desp", clear_on_submit=True):
            data_d = st.date_input("Data", value=datetime.now())
            desc = st.text_input("Descrição")
            valor = st.number_input("Valor", min_value=0.0)
            if st.form_submit_button("Salvar Despesa"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(data_d), desc, valor])
                st.rerun()
    with c2:
        df_d = get_data(ws_despesas)
        if not df_d.empty:
            df_d['data'] = pd.to_datetime(df_d['data'])
            m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
            df_f = df_d[(df_d['data'].dt.month == m) & (df_d['data'].dt.year == a)]
            st.dataframe(df_f, use_container_width=True)
            st.metric("Total do Mês", f"R$ {df_f['valor'].sum():,.2f}")

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Resumo Financeiro")
    seletor_mes()
    
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    
    m, a = st.session_state.data_filtro.month, st.session_state.data_filtro.year
    
    # Filtrar Reservas por mês de Entrada
    if not df_res.empty:
        df_res['entrada'] = pd.to_datetime(df_res['entrada'])
        df_res_f = df_res[(df_res['entrada'].dt.month == m) & (df_res['entrada'].dt.year == a)]
        receita = df_res_f['total'].sum()
    else: receita = 0
    
    # Filtrar Despesas
    if not df_desp.empty:
        df_desp['data'] = pd.to_datetime(df_desp['data'])
        df_desp_f = df_desp[(df_desp['data'].dt.month == m) & (df_desp['data'].dt.year == a)]
        gastos = df_desp_f['valor'].sum()
    else: gastos = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Faturamento (Entradas)", f"R$ {receita:,.2f}")
    col2.metric("Despesas do Mês", f"R$ {gastos:,.2f}", delta=-gastos)
    col3.metric("Lucro Líquido", f"R$ {receita - gastos:,.2f}")
    
    st.divider()
    st.subheader("Gráfico de Fluxo")
    if receita > 0 or gastos > 0:
        st.bar_chart(pd.DataFrame({"Valores": [receita, gastos]}, index=["Receita", "Despesas"]))

# --- MÓDULO RESERVAS ---
elif menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    df_res = get_data(ws_reservas)
    st.dataframe(df_res, use_container_width=True)
