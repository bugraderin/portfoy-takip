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
    # Streamlit Secrets üzerinden TOML formatındaki anahtarı okur
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # Tablo ve sayfa isimlerini bağlar
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Bağlantı Hatası: Lütfen Secrets ayarlarını ve Sheets adını kontrol edin. Hata: {e}")
    st.stop()
 
# --- 2. VERİ GİRİŞ FORMU ---
enstrumanlar = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Döviz', 'Kripto', 'Mevduat', 'BES']
 
with st.sidebar:
    st.subheader("Yeni Veri Girişi")
    st.caption("Değerleri yazdıktan sonra en alttaki butona basın.")
    
    # Form yapısı, her girişte sayfanın yenilenmesini engeller
    with st.form("veri_formu", clear_on_submit=True):
        yeni_degerler = []
        for e in enstrumanlar:
            val = st.number_input(f"{e} (TL)", min_value=0.0, step=100.0)
            yeni_degerler.append(val)
        
        submit = st.form_submit_button("Buluta Kaydet")
 
if submit:
    # Yeni satırı oluştur ve Sheets'e ekle
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.success("✅ Veriler kaydedildi!")
    st.rerun()
 
# --- 3. ANALİZ VE GÖRSELLEŞTİRME ---
# Sheets'ten tüm verileri çek
data = worksheet.get_all_records()
 
if data:
    df = pd.DataFrame(data)
    
    # 1. Sütunların sayısal olduğundan emin ol
    for col in enstrumanlar:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 2. Tarih sütununu işle ve sırala
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih']).dt.date
        df = df.sort_values('tarih')
    
    # 3. Toplam portföy değerini hesapla
    df['Toplam'] = df[enstrumanlar].sum(axis=1)
 
    # Özet Kartları Bölümü
    col1, col2, col3 = st.columns(3)
    guncel_toplam = df['Toplam'].iloc[-1]
    
    col1.metric("Güncel Toplam Portföy", f"{guncel_toplam:,.2f} TL")
    
    if len(df) > 1:
        onceki_toplam = df['Toplam'].iloc[-2]
        degisim = guncel_toplam - onceki_toplam
        yuzde = (degisim / onceki_toplam) * 100
        col2.metric("Son Değişim (TL)", f"{degisim:,.2f} TL", f"{yuzde:.2f}%")
    
    col3.metric("Toplam Kayıt Sayısı", len(df))
 
    st.divider()
 
    # Grafikler Bölümü
    tab1, tab2 = st.tabs(["📈 Zaman İçindeki Gelişim", "🥧 Güncel Dağılım"])
    
    with tab1:
        st.subheader("Toplam Varlık Değişim Grafiği")
        # Zaman serisi grafiği
        st.area_chart(df.set_index('tarih')['Toplam'])
        
    with tab2:
        st.subheader("Varlık Dağılımı (Son Durum)")
        son_durum = df[enstrumanlar].iloc[-1]
        
        # Sadece değeri 0'dan büyük olanları grafiğe ekle
        pastane_verisi = son_durum[son_durum > 0]
        
        if not pastane_verisi.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.pie(pastane_verisi, labels=pastane_verisi.index, autopct='%1.1f%%', startangle=140)
            ax.axis('equal')
            st.pyplot(fig)
        else:
            st.warning("Pasta grafiği için henüz 0'dan büyük bir değer girilmedi.")
 
    # Veri Tablosu Görüntüleyici
    with st.expander("Geçmiş Veri Tablosunu Gör"):
        st.dataframe(df)
else:
    st.info("💡 Henüz bir veri kaydı bulunamadı. Lütfen sol menüden ilk değerlerinizi girip 'Buluta Kaydet'e basın.")
