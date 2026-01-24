import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Finansal Portföy Takibi", layout="wide")

@st.cache_resource
def get_gc():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def get_data_from_sheet(sheet_name):
    try:
        gc = get_gc()
        sh = gc.open("portfoyum")
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) > 0:
            headers = [str(h).strip() for h in data[0]]
            df = pd.DataFrame(data[1:], columns=headers)
            return df
        return pd.DataFrame()
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ Google Kota Sınırı: Lütfen 1-2 dakika bekleyip sayfayı yenileyin.")
        return pd.DataFrame()

def write_to_sheet(sheet_name, row):
    try:
        gc = get_gc()
        sh = gc.open("portfoyum")
        ws = sh.worksheet(sheet_name)
        ws.append_row(row)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Yazma hatası: {e}")
        return False

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

# --- SEKME 1: GENEL DURUM ---
with tab_ana:
    st.subheader("Varlık Güncelleme")
    with st.form("v_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        v_altin = c1.number_input("Altın", min_value=0.0)
        v_doviz = c2.number_input("Döviz", min_value=0.0)
        v_hisse = c3.number_input("Hisse", min_value=0.0)
        v_kripto = c4.number_input("Kripto", min_value=0.0)
        v_mevduat = c5.number_input("Mevduat", min_value=0.0)
        
        if st.form_submit_button("Varlıkları Kaydet"):
            row = [datetime.now().strftime('%Y-%m-%d'), v_altin, v_doviz, v_hisse, v_kripto, v_mevduat]
            if write_to_sheet("Varlik_Miktarlari", row):
                st.success("Kaydedildi!")
                time.sleep(1)
                st.rerun()

# --- SEKME 2: PORTFÖY V2 (YENİ SÜTUN YAPISINA UYGUN) ---
with tab_fon_v2:
    st.subheader("Fon Portföy Girişi")
    df_l = get_data_from_sheet("Fon_Listesi")
    
    if not df_l.empty:
        f_opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        sec_f = st.selectbox("Fon Seçiniz:", options=f_opts, index=None)
        
        if sec_f:
            kod, ad = sec_f.split(" - ")[0], sec_f.split(" - ")[1]
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            lot = c2.number_input("Lot Miktarı:", min_value=0.0, step=0.01)
            
            p_sheet = "TefasFonVerileri" if src == "Tefas" else "BefasFonVerileri"
            df_p = get_data_from_sheet(p_sheet)
            
            # Yeni yapıda (Tarih, Fon Kodu, Fon Adı, Son Fiyat) olduğu için Fon Kodu sütunundan eşleştiriyoruz
            f_match = df_p[df_p['Fon Kodu'] == kod] if not df_p.empty else pd.DataFrame()
            
            fiyat = 0.0
            if not f_match.empty:
                try:
                    # 'Son Fiyat' başlığını kullanarak veriyi alıyoruz
                    raw_price = str(f_match.iloc[-1]['Son Fiyat']).strip().replace(',', '.')
                    fiyat = float(raw_price) if raw_price else 0.0
                    st.info(f"💰 Birim Fiyat: {fiyat} TL | Toplam: {lot*fiyat:,.2f} TL")
                except:
                    st.warning("Fiyat sütunu okunamadı, formatı kontrol edin.")

            if st.button("PORTFÖYE EKLE"):
                # 1. Veri_Giris'e ana işlem kaydı
                row_main = [datetime.now().strftime('%Y-%m-%d'), kod, ad, lot, fiyat, lot*fiyat, src]
                if write_to_sheet("Veri_Giris", row_main):
                    
                    # 2. Eğer fiyat sayfasında fon yoksa, yeni yapıya göre (Tarih, Kod, Ad, Fiyat) ekle
                    if f_match.empty:
                        # [Tarih, Fon Kodu, Fon Adı, Son Fiyat]
                        row_price = [datetime.now().strftime('%Y-%m-%d'), kod, ad, 0]
                        write_to_sheet(p_sheet, row_price)
                    
                    st.success("İşlem Başarılı!")
                    time.sleep(1)
                    st.rerun()

    st.divider()
    st.subheader("Son Fon İşlemleri")
    st.dataframe(get_data_from_sheet("Veri_Giris"), use_container_width=True)
