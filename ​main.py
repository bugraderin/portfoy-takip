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

# --- YARDIMCI FONKSİYON: GÜNCEL BAKİYE ---
def get_son_bakiye_ve_limit():
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

# (Portföy, Gelir ve Bütçe sekmeleri önceki sade yapısıyla aynı kalmıştır)

# --- SEKME 3: GİDERLER (PASTA GRAFİK EKLENDİ) ---
with tab_gider:
    st.subheader("💸 Gider Girişi")
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{kalan_bakiye:,.0f} TL**")
    
    with st.form("gi_form", clear_on_submit=True):
        st.write("### 🏷️ Harcama Kalemleri")
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
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [x or 0 for x in kalemler], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                st.success(f"Kaydedildi. Yeni bakiye: {yeni_kalan} TL")
                st.rerun()

    # --- ÜNLÜ PASTA GRAFİĞİ ---
    st.divider()
    st.subheader("🥧 Harcama Dağılımı")
    
    data_g = ws_gider.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        # Tarih hariç tüm sütunların toplamını al
        kategoriler = ["Genel Giderler", "Market", "Kira", "Aidat", "Kredi Kartı", "Kredi", "Eğitim", "Araba", "Seyahat", "Sağlık", "Çocuk", "Toplu Taşıma"]
        
        # Sütunların sayısal olduğundan emin ol ve toplamlarını hesapla
        for col in kategoriler:
            if col in df_g.columns:
                df_g[col] = pd.to_numeric(df_g[col], errors='coerce').fillna(0)
        
        toplamlar = df_g[kategoriler].sum()
        
        # Sadece harcama yapılan (toplamı 0'dan büyük olan) kategorileri göster
        pasta_data = toplamlar[toplamlar > 0].reset_index()
        pasta_data.columns = ['Kategori', 'Tutar']
        
        if not pasta_data.empty:
            fig_pie = px.pie(
                pasta_data, 
                values='Tutar', 
                names='Kategori', 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("Henüz harcama verisi bulunmuyor.")

# (Diğer sekmeler aynı şekilde devam eder...)
