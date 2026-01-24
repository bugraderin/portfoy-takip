import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Portfoy Takip", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    spreadsheet = client.open("portfoyum")
    
    # Sayfalar (Görseldeki isimlerinle birebir)
    ws_v_miktar = spreadsheet.worksheet("Varlik_Miktarlari")
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

def get_data(ws):
    time.sleep(0.2) # Kotayı korumak için çok kısa bekleme
    data = ws.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum & Manuel Giriş", "🚀 Portföy V2 (Fon)"])

# --- SEKME 1: GENEL DURUM & KAYIT ---
with tab_ana:
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        st.subheader("📥 Varlık Güncelle")
        # Bu form Varlik_Miktarlari sayfasına yazar
        with st.form("varlik_form", clear_on_submit=True):
            f_altin = st.number_input("Altın Miktarı", min_value=0.0)
            f_doviz = st.number_input("Döviz Miktarı", min_value=0.0)
            f_hisse = st.number_input("Hisse Senedi", min_value=0.0)
            f_kripto = st.number_input("Kripto", min_value=0.0)
            f_mevduat = st.number_input("Mevduat", min_value=0.0)
            
            if st.form_submit_button("Varlıkları Kaydet"):
                # Görseldeki Varlik_Miktarlari sütun sırasına göre (Tarih, Altin, Doviz...)
                yeni_veri = [datetime.now().strftime('%Y-%m-%d'), f_altin, f_doviz, f_hisse, f_kripto, f_mevduat]
                ws_v_miktar.append_row(yeni_veri)
                st.success("Varlik_Miktarlari sayfasına kaydedildi!")
                st.rerun()

    with col_r:
        st.subheader("📈 Güncel Durum")
        df_m = get_data(ws_v_miktar)
        if not df_m.empty:
            last = df_m.iloc[-1].copy()
            m1, m2, m3 = st.columns(3)
            m1.metric("Altın", f"{last.get('Altin', 0)}")
            m2.metric("Döviz", f"{last.get('Doviz', 0)}")
            m3.metric("Hisse", f"{last.get('HisseSenedi', 0)}")

# --- SEKME 2: PORTFÖY V2 (FON KAYIT) ---
with tab_fon_v2:
    st.subheader("🎯 Detaylı Fon Alımı")
    # Bu bölüm Veri_Giris sayfasına yazar
    df_list = get_data(ws_fon_listesi)
    
    if not df_list.empty:
        f_names = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_list.iterrows()]
        sec_fon = st.selectbox("Fon Seç:", options=f_names, index=None)
        
        if sec_fon:
            f_kod = sec_fon.split(" - ")[0]
            f_ad = sec_fon.split(" - ")[1]
            
            c1, c2, c3 = st.columns(3)
            src = c1.radio("Kaynak:", ["Tefas", "Befas"])
            f_lot = c2.number_input("Lot:", min_value=0.0, step=0.1)
            
            ws_f_data = ws_tefas if src == "Tefas" else ws_befas
            df_fiyat = get_data(ws_f_data)
            f_match = df_fiyat[df_fiyat['Fon Kodu'] == f_kod] if not df_fiyat.empty else pd.DataFrame()
            
            if not f_match.empty:
                f_birim = float(f_match.iloc[0]['Son Fiyat'])
                f_toplam = f_lot * f_birim
                st.info(f"Birim Fiyat: {f_birim} TL | Toplam: {f_toplam:,.2f} TL")
                
                if st.button("Fonu Portföye Ekle"):
                    # Veri_Giris sayfasına kayıt
                    ws_veri_giris.append_row([datetime.now().strftime('%Y-%m-%d'), f_kod, f_ad, f_lot, f_birim, f_toplam, src])
                    st.success(f"{f_kod} Veri_Giris sayfasına eklendi!")
                    st.rerun()
    
    st.divider()
    st.write("📋 Son Fon İşlemleri (Veri_Giris)")
    st.dataframe(get_data(ws_veri_giris), use_container_width=True)
