import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip Paneli", layout="wide")
st.title("💰 Kişisel Finans ve Portföy Yönetimi")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Sayfaları Tanımla
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Sayfa Bağlantı Hatası: {e}. Lütfen Sheets sayfa isimlerini kontrol edin.")
    st.stop()

# --- 2. CSS: TEMİZ GİRİŞ ALANLARI ---
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- 3. ANA SEKMELER (TABS) ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Gidere Ayrılan Tutar"])

# --- SEKME 1: PORTFÖY YÖNETİMİ (Mevcut Kodun) ---
with tab_portfoy:
    st.subheader("Portföy Durumu")
    # (Buraya önceki portföy kodlarını olduğu gibi yapıştırabilirsin)
    st.info("Portföy verileri buraya gelecek.")

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("Gelir Girişi")
    gelir_kalemleri = ["Maaş", "Prim&Promosyon", "Yatırımlar"]
    with st.form("gelir_formu", clear_on_submit=True):
        g_inputs = {k: st.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="Tutarı yazın...", format="%d") for k in gelir_kalemleri}
        g_submit = st.form_submit_button("Geliri Kaydet", use_container_width=True)
    
    if g_submit:
        g_row = [datetime.now().strftime('%Y-%m-%d')] + [g_inputs[k] if g_inputs[k] is not None else 0 for k in gelir_kalemleri]
        ws_gelir.append_row(g_row, value_input_option='RAW')
        st.success("Gelir kaydedildi!")

# --- SEKME 3: GİDERLER ---
with tab_gider:
    st.subheader("Gider Girişi")
    gider_kalemleri = ["Genel Giderler", "Market", "Kira", "Aidat", "Kredi Kartı", "Kredi", "Eğitim", "Araba", "Seyahat", "Sağlık", "Çocuk", "Toplu Taşıma"]
    
    # Formu sütunlara bölerek daha düzenli gösterelim
    with st.form("gider_formu", clear_on_submit=True):
        col1, col2 = st.columns(2)
        gi_inputs = {}
        for i, k in enumerate(gider_kalemleri):
            target_col = col1 if i < len(gider_kalemleri)/2 else col2
            gi_inputs[k] = target_col.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="0", format="%d")
        
        gi_submit = st.form_submit_button("Gideri Kaydet", use_container_width=True)
    
    if gi_submit:
        gi_row = [datetime.now().strftime('%Y-%m-%d')] + [gi_inputs[k] if gi_inputs[k] is not None else 0 for k in gider_kalemleri]
        ws_gider.append_row(gi_row, value_input_option='RAW')
        st.success("Gider kaydedildi!")

# --- SEKME 4: GİDERE AYRILAN TUTAR ---
with tab_ayrilan:
    st.subheader("Gidere Ayrılan Bütçe Takibi")
    ayrilan_kalemler = ["Ayrılan Tutar", "Kalan", "Devreden"]
    with st.form("ayrilan_formu", clear_on_submit=True):
        a_inputs = {k: st.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="Tutarı yazın...", format="%d") for k in ayrilan_kalemler}
        a_submit = st.form_submit_button("Bütçeyi Güncelle", use_container_width=True)
    
    if a_submit:
        a_row = [datetime.now().strftime('%Y-%m-%d')] + [a_inputs[k] if a_inputs[k] is not None else 0 for k in ayrilan_kalemler]
        ws_ayrilan.append_row(a_row, value_input_option='RAW')
        st.success("Bütçe verisi güncellendi!")
