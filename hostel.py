import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime
from streamlit_calendar import calendar

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hostel Pro Cloud", layout="wide", page_icon="🏨")

# --- INICIALIZAÇÃO DE ESTADOS ---
if "data_filtro_despesas" not in st.session_state:
    st.session_state.data_filtro_despesas = datetime.now().replace(day=1)

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
                "start": str(row['entrada']),
                "end": str(row['saida']),
                "color": color,
                "extendedProps": {"hospedes": row['hospedes'], "total": row['total']}
            })

        calendar_options = {
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek"},
            "initialView": "dayGridMonth",
            "locale": "pt-br",
        }

        state = calendar(events=calendar_events, options=calendar_options, key='hostel_calendar')
        
        if state.get("eventClick"):
            event_id = state["eventClick"]["event"]["title"] + state["eventClick"]["event"]["start"]
            if "last_event_id" not in st.session_state or st.session_state.last_event_id != event_id:
                st.session_state.last_event_id = event_id
                detalhes_reserva(state["eventClick"]["event"])
        else:
            st.session_state.last_event_id = None

# --- MÓDULO DESPESAS ---
elif menu == "Despesas":
    st.header("💸 Controlo de Despesas")
    
    # Navegação por Mês
    col_mes1, col_mes2, col_mes3 = st.columns([1, 2, 1])
    
    with col_mes1:
        if st.button("⬅️ Mês Anterior"):
            nova_data = st.session_state.data_filtro_despesas - pd.DateOffset(months=1)
            st.session_state.data_filtro_despesas = nova_data
            st.rerun()
            
    with col_mes2:
        mes_ano_texto = st.session_state.data_filtro_despesas.strftime("%B / %Y")
        st.markdown(f"<h3 style='text-align: center;'>{mes_ano_texto.capitalize()}</h3>", unsafe_allow_html=True)
        
    with col_mes3:
        if st.button("Próximo Mês ➡️"):
            nova_data = st.session_state.data_filtro_despesas + pd.DateOffset(months=1)
            st.session_state.data_filtro_despesas = nova_data
            st.rerun()

    st.divider()

    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Nova Despesa")
        with st.form("form_desp", clear_on_submit=True):
            data_d = st.date_input("Data", value=datetime.now())
            desc = st.text_input("Descrição")
            valor = st.number_input("Valor", min_value=0.0)
            if st.form_submit_button("Salvar Despesa"):
                ws_despesas.append_row([int(datetime.now().timestamp()), str(data_d), desc, valor])
                st.success("Despesa registada!")
                st.rerun()

    with c2:
        df_d = get_data(ws_despesas)
        if not df_d.empty:
            # Converter a coluna de data para filtrar
            df_d['data'] = pd.to_datetime(df_d['data'])
            
            # Filtrar pelo mês e ano selecionados
            mes_sel = st.session_state.data_filtro_despesas.month
            ano_sel = st.session_state.data_filtro_despesas.year
            
            df_filtrado = df_d[(df_d['data'].dt.month == mes_sel) & (df_d['data'].dt.year == ano_sel)]
            
            st.subheader(f"Registos de {mes_ano_texto}")
            if not df_filtrado.empty:
                st.dataframe(df_filtrado, use_container_width=True)
                total_mes = df_filtrado['valor'].sum()
                st.info(f"**Total do mês:** R$ {total_mes:,.2f}")
            else:
                st.warning("Nenhuma despesa para este período.")

# --- MÓDULO RESERVAS ---
elif menu == "Reservas":
    st.header("📋 Gestão de Reservas")
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("form_reserva", clear_on_submit=True):
            nome = st.text_input("Nome do Hóspede")
            hospedes = st.number_input("Hóspedes", min_value=1)
            quarto = st.selectbox("Quarto", ["Master", "Studio", "Triplo"])
            entrada = st.date_input("Entrada")
            saida = st.date_input("Saída")
            total = st.number_input("Total (R$)", min_value=0.0)
            if st.form_submit_button("Salvar"):
                if (saida - entrada).days > 0:
                    ws_reservas.append_row([int(datetime.now().timestamp()), nome, hospedes, quarto, str(entrada), str(saida), (saida-entrada).days, total])
                    st.rerun()
                else: st.error("Datas inválidas.")
    with col2:
        df_res = get_data(ws_reservas)
        if not df_res.empty: st.dataframe(df_res)

# --- MÓDULO FINANCEIRO ---
elif menu == "Financeiro":
    st.header("💰 Financeiro")
    df_res = get_data(ws_reservas)
    df_desp = get_data(ws_despesas)
    r = df_res['total'].sum() if not df_res.empty else 0
    g = df_desp['valor'].sum() if not df_desp.empty else 0
    st.metric("Faturamento Total", f"R$ {r:,.2f}")
    st.metric("Despesas Totais", f"R$ {g:,.2f}", delta=-g)
    st.metric("Lucro Líquido", f"R$ {r-g:,.2f}")
