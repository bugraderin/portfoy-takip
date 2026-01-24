import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portfoy Takip", layout="wide")

# --- 1. BAĞLANTI & CACHE (KOTA DOSTU) ---
@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    spreadsheet = client.open("portfoyum")
    
    # Sayfalar - Görselindeki isimler
    ws_v_miktar = spreadsheet.worksheet("Varlik_Miktarlari")
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# Veri çekme fonksiyonu (Sadece ihtiyaç olduğunda çalışır)
def get_data(ws):
    # API limitine takılmamak için küçük bir bekleme
    time.sleep(0.5) 
    data = ws.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()

# --- SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2 (Fon)"])

# --- SEKME 1: GENEL DURUM ---
with tab_ana:
    df_m = get_data(ws_v_miktar)
    if not df_m.empty:
        # Son veriyi al
        last_row = df_m.iloc[-1].copy()
        for col in last_row.index:
            if col != 'tarih':
                last_row[col] = pd.to_numeric(last_row[col], errors='coerce') or 0
        
        # Ekranın en üstünde ana varlıkları göster
        cols = st.columns(4)
        cols[0].metric("Altın", f"{last_row.get('Altin', 0):,.0f}")
        cols[1].metric("Döviz", f"{last_row.get('Doviz', 0):,.0f}")
        cols[2].metric("Hisse", f"{last_row.get('HisseSenedi', 0):,.0f}")
        cols[3].metric("Kripto", f"{last_row.get('Kripto', 0):,.0f}")

# --- SEKME 2: PORTFÖY V2 ---
with tab_fon_v2:
    st.subheader("📥 Yeni Fon Girişi")
    df_list = get_data(ws_fon_listesi)
    
    if not df_list.empty:
        f_names = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_list.iterrows()]
        sec_fon = st.selectbox("Fon Seçin:", options=f_names, index=None)
        
        if sec_fon:
            f_kod = sec_fon.split(" - ")[0]
            f_ad = sec_fon.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            src = c1.radio("Kaynak:", ["Tefas", "Befas"])
            f_lot = c2.number_input("Lot:", min_value=0.0, step=0.01)
            
            # Fiyatı çek
            ws_f_data = ws_tefas if src == "Tefas" else ws_befas
            df_fiyat = get_data(ws_f_data)
            
            f_match = df_fiyat[df_fiyat['Fon Kodu'] == f_kod] if not df_fiyat.empty else pd.DataFrame()
            
            if not f_match.empty:
                f_birim = float(f_match.iloc[0]['Son Fiyat'])
                f_toplam = f_lot * f_birim
                st.info(f"Birim Fiyat: {f_birim} | Toplam: {f_toplam:,.2f} TL")
                
                if st.button("Portföye Kaydet"):
                    ws_veri_giris.append_row([datetime.now().strftime('%Y-%m-%d'), f_kod, f_ad, f_lot, f_birim, f_toplam, src])
                    st.success("Kaydedildi!")
                    st.rerun()

    st.divider()
    st.write("📋 Kayıtlı İşlemler (Veri_Giris)")
    st.dataframe(get_data(ws_veri_giris), use_container_width=True)
