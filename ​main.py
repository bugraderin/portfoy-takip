import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy ve Gider Yönetimi", layout="wide")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# CSS: Artı/Eksi butonlarını gizler
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYON: GÜNCEL BAKİYE ---
def get_son_bakiye_ve_limit():
    """Bütçe sayfasındaki son kalan tutarı ve tanımlı limiti getirir."""
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son['Kalan']), float(son['Ayrılan Tutar'])
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar], value_input_option='RAW')
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        guncel = df_p.iloc[-1]

        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Varlık Gelişimi")
        st.plotly_chart(fig_line, use_container_width=True)

# --- SEKME 3: GİDERLER (DEVREDEN SİLİNDİ) ---
with tab_gider:
    st.subheader("💸 Gider Girişi")
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{kalan_bakiye:,.0f} TL**")
    
    with st.form("gi_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        genel = c1.number_input("Genel Giderler", min_value=0, value=None)
        market = c2.number_input("Market", min_value=0, value=None)
        kira = c3.number_input("Kira", min_value=0, value=None)
        
        c4, c5, c6 = st.columns(3)
        aidat = c4.number_input("Aidat", min_value=0, value=None)
        kk = c5.number_input("Kredi Kartı", min_value=0, value=None)
        kredi = c6.number_input("Kredi", min_value=0, value=None)
        
        c7, c8, c9 = st.columns(3)
        egitim = c7.number_input("Eğitim", min_value=0, value=None)
        araba = c8.number_input("Araba", min_value=0, value=None)
        seyahat = c9.number_input("Seyahat", min_value=0, value=None)
        
        c10, c11, c12 = st.columns(3)
        saglik = c10.number_input("Sağlık", min_value=0, value=None)
        cocuk = c11.number_input("Çocuk", min_value=0, value=None)
        ulashim = c12.number_input("Toplu Taşıma", min_value=0, value=None)

        if st.form_submit_button("✅ Harcamayı Kaydet"):
            kalemler = [genel, market, kira, aidat, kk, kredi, egitim, araba, seyahat, saglik, cocuk, ulashim]
            toplam_h = sum([x or 0 for x in kalemler])
            
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                
                # Giderler Sayfasına Yaz (Tarih + 12 Kalem)
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [x or 0 for x in kalemler], value_input_option='RAW')
                
                # Bütçe Sayfasına Yaz (Tarih, Ayrılan Tutar, Kalan)
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                
                st.success(f"Kaydedildi. Yeni bakiye: {yeni_kalan} TL")
                st.rerun()

# --- SEKME 4: BÜTÇE PLANI ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Tanımla")
    with st.form("a_form", clear_on_submit=True):
        y_lim = st.number_input("Aylık Limit", min_value=0, value=None)
        if st.form_submit_button("Bütçeyi Başlat"):
            # Tarih, Ayrılan Tutar, Kalan
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), y_lim or 0, y_lim or 0], value_input_option='RAW')
            st.success("Yeni bütçe başlatıldı.")
            st.rerun()

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    with st.form("g_form", clear_on_submit=True):
        m = st.number_input("Maaş", min_value=0, value=None)
        p = st.number_input("Prim", min_value=0, value=None)
        y = st.number_input("Yatırım", min_value=0, value=None)
        if st.form_submit_button("Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0], value_input_option='RAW')
            st.success("Gelir eklendi.")
            st.rerun()
