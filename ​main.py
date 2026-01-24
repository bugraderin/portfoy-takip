import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portfoy Takip", layout="wide")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Görseldeki birebir sayfa isimleri
    ws_v_miktar = spreadsheet.worksheet("Varlik_Miktarlari")
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas = spreadsheet.worksheet("BefasFonVerileri")
    
    # Diğer varlık sayfaları (Gerekirse veri çekmek için)
    ws_altin = spreadsheet.worksheet("Altin")
    ws_doviz = spreadsheet.worksheet("Doviz")
    ws_hisse = spreadsheet.worksheet("HisseSenedi")
    ws_kripto = spreadsheet.worksheet("Kripto")
    ws_mevduat = spreadsheet.worksheet("Mevduat")

except Exception as e:
    st.error(f"Bağlantı Hatası: {e}. Sayfa isimlerini kontrol et!"); st.stop()

# Güvenli okuma fonksiyonu (Hata vermez)
def safe_read(ws):
    try:
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = [c.strip() for c in df.columns]
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2 (Fon)"])

# --- SEKME 1: GENEL DURUM (Varlik_Miktarlari üzerinden) ---
with tab_ana:
    st.header("💰 Mevcut Varlıklar")
    df_m = safe_read(ws_v_miktar)
    
    if not df_m.empty:
        # Son satırı alıp sayıya çeviriyoruz
        last_row = df_m.iloc[-1].copy()
        cols = [c for c in df_m.columns if c.lower() != 'tarih']
        
        for c in cols:
            last_row[c] = pd.to_numeric(last_row[c], errors='coerce') or 0
        
        # Metrikler
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Altın", f"{last_row.get('Altin', 0):,.0f}")
        c2.metric("Döviz", f"{last_row.get('Doviz', 0):,.0f}")
        c3.metric("Hisse", f"{last_row.get('HisseSenedi', 0):,.0f}")
        c4.metric("Kripto", f"{last_row.get('Kripto', 0):,.0f}")

        # Grafik
        df_m['tarih'] = pd.to_datetime(df_m.iloc[:, 0], errors='coerce')
        st.plotly_chart(px.line(df_m, x='tarih', y=cols, title="Varlık Değişimi"), use_container_width=True)

# --- SEKME 2: PORTFÖY V2 (Fon_Listesi & Veri_Giris üzerinden) ---
with tab_fon_v2:
    st.header("🚀 Detaylı Fon Girişi")
    
    df_l = safe_read(ws_fon_listesi)
    if not df_l.empty:
        options = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        secilen = st.selectbox("Fon Seç:", options=options, index=None)
        
        if secilen:
            f_kod = secilen.split(" - ")[0]
            f_ad = secilen.split(" - ")[1]
            
            col1, col2 = st.columns(2)
            kaynak = col1.radio("Kaynak:", ["Tefas", "Befas"])
            f_lot = col2.number_input("Lot Miktarı:", min_value=0.0, step=0.01)
            
            ws_f_data = ws_tefas if kaynak == "Tefas" else ws_befas
            df_fiyatlar = safe_read(ws_f_data)
            
            f_row = df_fiyatlar[df_fiyatlar['Fon Kodu'] == f_kod] if not df_fiyatlar.empty else pd.DataFrame()
            
            if not f_row.empty:
                f_fiyat = float(f_row.iloc[0]['Son Fiyat'])
                f_toplam = f_lot * f_fiyat
                st.success(f"Birim Fiyat: {f_fiyat} | Toplam Tutar: {f_toplam:,.2f} TL")
                
                if st.button("📥 Veri_Giris Sayfasına Kaydet"):
                    ws_veri_giris.append_row([datetime.now().strftime('%Y-%m-%d'), f_kod, f_ad, f_lot, f_fiyat, f_toplam, kaynak])
                    st.rerun()
            else:
                st.warning("Fiyat bulunamadı!")

    st.divider()
    st.subheader("📋 Veri_Giris Tablosu")
    st.dataframe(safe_read(ws_veri_giris), use_container_width=True)
