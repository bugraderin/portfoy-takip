import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Portföy Takip Sistemi", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# KOTAYI KORUMAK İÇİN CACHE (120 Saniye)
@st.cache_data(ttl=120)
def get_data_cached(sheet_name):
    try:
        client = get_sheets_client()
        spreadsheet = client.open("portfoyum")
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) > 0:
            headers = [str(h).strip() for h in data[0]]
            df = pd.DataFrame(data[1:], columns=headers)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"{sheet_name} okunamadı: {e}")
        return pd.DataFrame()

# Yazma işlemleri için doğrudan erişim
def get_worksheet_direct(sheet_name):
    client = get_sheets_client()
    return client.open("portfoyum").worksheet(sheet_name)

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

# --- SEKME 1: GENEL DURUM (Varlik_Miktarlari) ---
with tab_ana:
    st.subheader("Varlık Girişi")
    with st.form("v_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        v_altin = c1.number_input("Altın", min_value=0.0)
        v_doviz = c2.number_input("Döviz", min_value=0.0)
        v_hisse = c3.number_input("Hisse", min_value=0.0)
        v_kripto = c4.number_input("Kripto", min_value=0.0)
        v_mevduat = c5.number_input("Mevduat", min_value=0.0)
        
        if st.form_submit_button("Varlıkları Kaydet"):
            ws = get_worksheet_direct("Varlik_Miktarlari")
            ws.append_row([datetime.now().strftime('%Y-%m-%d'), v_altin, v_doviz, v_hisse, v_kripto, v_mevduat])
            st.cache_data.clear() # Veri değiştiği için önbelleği sıfırla
            st.success("Varlıklar başarıyla kaydedildi.")
            time.sleep(1)
            st.rerun()

# --- SEKME 2: PORTFÖY V2 (Fon İşlemleri) ---
with tab_fon_v2:
    st.subheader("Yeni Fon Alım Kaydı")
    
    df_l = get_data_cached("Fon_Listesi")
    if not df_l.empty:
        # Başlıkların varlığından emin olarak fonları listele
        f_opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        sec_f = st.selectbox("Fon Seçiniz:", options=f_opts, index=None)
        
        if sec_f:
            kod = sec_f.split(" - ")[0]
            ad = sec_f.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            lot = c2.number_input("Alınan Lot:", min_value=0.0, step=0.01)
            
            # Fiyat verisini çek
            price_sheet = "TefasFonVerileri" if src == "Tefas" else "BefasFonVerileri"
            df_p = get_data_cached(price_sheet)
            f_match = df_p[df_p['Fon Kodu'] == kod] if not df_p.empty else pd.DataFrame()
            
            fiyat = 0.0
            if not f_match.empty:
                # Sayısal dönüşüm güvenliği
                raw_price = str(f_match.iloc[0]['Son Fiyat']).strip().replace(',', '.')
                try:
                    fiyat = float(raw_price) if raw_price else 0.0
                    st.info(f"💰 Güncel Fiyat: {fiyat} TL | Toplam: {lot*fiyat:,.2f} TL")
                except:
                    st.warning("Fiyat sütununda sayısal olmayan değer var.")

            if st.button("KAYDET", use_container_width=True):
                # 1. Veri_Giris sayfasına ana işlemi yaz
                ws_entry = get_worksheet_direct("Veri_Giris")
                ws_entry.append_row([datetime.now().strftime('%Y-%m-%d'), kod, ad, lot, fiyat, lot*fiyat, src])
                
                # 2. Eğer fiyat listesinde fon yoksa ekle (Apps Script'in tanıması için)
                if f_match.empty:
                    ws_price_list = get_worksheet_direct(price_sheet)
                    ws_price_list.append_row([kod, "", 0]) # Kod, Ad(Boş), Fiyat(0)
                
                st.cache_data.clear()
                st.success(f"{kod} işlemi Veri_Giris sayfasına kaydedildi.")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("Son İşlemler (Veri_Giris)")
    df_history = get_data_cached("Veri_Giris")
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
