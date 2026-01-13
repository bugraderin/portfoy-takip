import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
 
# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Bizim Portföyümüz")
 
# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    # Streamlit Secrets üzerinden anahtarı okur
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # Tablo ve sayfa isimleri
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()
 
# --- 2. VERİ GİRİŞ FORMU ---
enstrumanlar = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Döviz', 'Kripto', 'Mevduat', 'BES']
 
with st.sidebar:
    st.subheader("Yeni Veri Girişi")
    with st.form("veri_formu", clear_on_submit=True):
        yeni_degerler = []
        for e in enstrumanlar:
            val = st.number_input(f"{e} (TL)", min_value=0.0, step=100.0)
            yeni_degerler.append(val)
        
        submit = st.form_submit_button("Buluta Kaydet")
 
if submit:
    # Google Sheets'e yeni satırı ekler
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.success("✅ Veriler kaydedildi! Sayfayı yenileyebilirsiniz.")
    st.rerun()
 
# --- 3. ANALİZ VE GÖRSELLEŞTİRME ---
# Tüm veriyi çek
data = worksheet.get_all_records()
 
if data:
    df = pd.DataFrame(data)
    
    # Sayısal sütunları temizle ve çevir
    for col in enstrumanlar:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Tarih sütununu işle
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih']).dt.date
        df = df.sort_values('tarih')
    
    # Toplam değerini hesapla
    df['Toplam'] = df[enstrumanlar].sum(axis=1)
 
    # Özet Kartları
    col1, col2, col3 = st.columns(3)
    guncel_toplam = df['Toplam'].iloc[-1]
    
    col1.metric("Güncel Toplam Portföy", f"{guncel_toplam:,.2f} TL")
    
    if len(df) > 1:
        degisim = guncel_toplam - df['Toplam'].iloc[-2]
        yuzde = (degisim / df['Toplam'].iloc[-2]) * 100
        col2.metric("Son Değişim (TL)", f"{degisim:,.2f} TL", f"{yuzde:.2f}%")
    
    col3.metric("Veri Kaydı Sayısı", len(df))
 
    st.divider()
 
    # Grafikler
    tab1, tab2 = st.tabs(["📈 Zaman İçindeki Gelişim", "🥧 Güncel Dağılım"])
    
    with tab1:
        st.subheader("Toplam Varlık Değişimi")
        st.line_chart(df.set_index('tarih')['Toplam'])
        
    with tab2:
        st.subheader("Varlık Dağılımı (Son Kayıt)")
        son_degerler = [df[e].iloc[-1] for e in enstrumanlar]
        fig1, ax1 = plt.subplots(figsize=(8, 5))
        # Sadece 0'dan büyük varlıkları göster
        labels = [e for i, e in enumerate(enstrumanlar) if son_degerler[i] > 0]
        sizes = [v for v in son_degerler if v > 0]
        
        if sizes:
            ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
            st.pyplot(fig1)
        else:
            st.warning("Grafik için veri bulunamadı.")
 
    # Veri Tablosu
    with st.expander("Geçmiş Kayıtları Düzenle/Gör"):
        st.dataframe(df)
else:
    st.warning("Henüz veri bulunamadı. Lütfen yan menüden ilk verinizi girin.")
