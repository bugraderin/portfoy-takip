import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Portföy Yönetim Paneli")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# --- 2. VARLIK TANIMLARI ---
enstruman_bilgi = {
    'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
    'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
}
enstrumanlar = list(enstruman_bilgi.keys())

# --- 3. UI: VERİ GİRİŞ ALANI ---
with st.sidebar:
    st.header("📥 Veri Girişi")
    with st.form("veri_formu", clear_on_submit=True):
        inputs = {}
        for e in enstrumanlar:
            # step=1.0 ve format="%d" ile ondalık karmaşasını bitirdik
            inputs[e] = st.number_input(
                f"{enstruman_bilgi[e]} {e} (TL)", 
                min_value=0, 
                step=1, 
                value=None, 
                placeholder="Örn: 600000",
                format="%d" 
            )
        submit = st.form_submit_button("🚀 Kaydet", use_container_width=True)

# CSS: Okları kaldırma
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

if submit:
    # Sayıları int (tam sayı) olarak zorlayarak gönderiyoruz
    kayit_verisi = [int(inputs[e]) if inputs[e] is not None else 0 for e in enstrumanlar]
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + kayit_verisi
    worksheet.append_row(yeni_satir, value_input_option='RAW') # RAW seçeneği veriyi olduğu gibi (sayı olarak) iletir
    st.toast("Veriler kaydedildi!", icon='✅')
    st.rerun()

# --- 4. VERİ İŞLEME ---
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
    df = df.dropna(subset=['tarih'])
    
    for col in enstrumanlar:
        if col in df.columns:
            # Okurken veriyi sayıya çevir
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['Toplam'] = df[enstrumanlar].sum(axis=1)
    df = df.sort_values('tarih')
    guncel = df.iloc[-1]

    # --- ÖZET VE ANALİZ BÖLÜMLERİ ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Varlık", f"{int(guncel['Toplam']):,} TL".replace(",", ".")) # TR Formatı Görünüm
    
    # ... (Grafik ve Performans Analizi kodları aynı kalıyor) ...
    # (Önceki başarılı çalışan grafik ve analiz bloklarını buraya ekleyebilirsiniz)

    # --- 8. GEÇMİŞ KAYITLAR ---
    st.divider()
    with st.expander("📄 Tüm Geçmiş Kayıtları Listele"):
        # Tablo görünümünde sayıları formatla
        st.dataframe(df.sort_values('tarih', ascending=False).style.format(subset=enstrumanlar + ['Toplam'], formatter="{:,.0f}"))
else:
    st.info("💡 Veri girişi yapın.")
