import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="centered")
st.title("📊 Bizim Portföyümüz")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
# Streamlit Secrets üzerinden anahtarı güvenli şekilde okur
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# Tablo isimlerinle birebir uyumlu
spreadsheet = client.open("portfoyum")
worksheet = spreadsheet.worksheet("Veri Sayfası")

# --- 2. VERİ GİRİŞ FORMU ---
with st.form("veri_formu"):
    st.subheader("Bugünkü Değerleri Girin")
    enstrumanlar = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Döviz', 'Kripto', 'Mevduat', 'BES']
    
    # Girişleri yan yana iki sütun yapalım
    cols = st.columns(2)
    yeni_degerler = []
    for i, e in enumerate(enstrumanlar):
        # Varsayılan olarak 0.0 gelir, sen kutuya yazacaksın
        val = cols[i % 2].number_input(f"{e} (TL)", min_value=0.0, step=100.0)
        yeni_degerler.append(val)
    
    submit = st.form_submit_button("Buluta Kaydet ve Analiz Et")

if submit:
    # Google Sheets'e yeni satırı ekler
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.success("✅ Veriler başarıyla 'Veri Sayfası'na kaydedildi!")

# --- 3. ANALİZ VE GÖRSELLEŞTİRME ---
# Tüm veriyi çek ve analiz et
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Sayısal değerlere çevir
for col in enstrumanlar:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
df['Toplam'] = df[enstrumanlar].sum(axis=1)

if not df.empty:
    st.divider()
    
    # Üst Bilgi Kartları (Metrics)
    son_toplam = df['Toplam'].iloc[-1]
    
    if len(df) >= 2:
        onceki_toplam = df['Toplam'].iloc[-2]
        fark = son_toplam - onceki_toplam
        degisim_yuzde = (fark / onceki_toplam) * 100
        st.metric("Güncel Toplam Varlık", f"{son_toplam:,.2f} TL", f"{degisim_yuzde:.2f}%")
    else:
        st.metric("Güncel Toplam Varlık", f"{son_toplam:,.2f} TL")

    # Grafik Bölümü
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.write("**Varlık Dağılımı**")
        fig1, ax1 = plt.subplots()
        ax1.pie(yeni_degerler, labels=enstrumanlar, autopct='%1.1f%%', startangle=140)
        st.pyplot(fig1)

    with col_chart2:
        st.write("**Zaman İçindeki Gelişim**")
        st.line_chart(df.set_index('tarih')['Toplam']) # Google Sheets'te ilk sütun adı 'tarih' olmalı

