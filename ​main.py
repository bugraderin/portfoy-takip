import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Finansal Portföy Takibi", layout="wide")

# Google Bağlantısını bir kez kurup saklıyoruz
@st.cache_resource
def get_gc():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# VERİ OKUMAYI CACHE'E ALIYORUZ (Kotanın baş düşmanı burasıdır)
@st.cache_data(ttl=300) # 5 Dakika boyunca Google'a sorma, kendi hafızandan oku
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
        # Kota hatası geldiğinde kullanıcıyı uyar ama uygulamayı çökertme
        if "429" in str(e):
            st.warning("⚠️ Google Kota Sınırı: Lütfen 2-3 dakika bekleyip sayfayı yenileyin.")
        else:
            st.error(f"Hata ({sheet_name}): {e}")
        return pd.DataFrame()

# VERİ YAZMA FONKSİYONU (Yazarken Cache kullanılmaz)
def write_to_sheet(sheet_name, row):
    try:
        gc = get_gc()
        sh = gc.open("portfoyum")
        ws = sh.worksheet(sheet_name)
        ws.append_row(row)
        # Veri değiştiği için cache'i temizle ki güncel hali gelsin
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Yazma hatası: {e}")
        return False

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

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
            success = write_to_sheet("Varlik_Miktarlari", [datetime.now().strftime('%Y-%m-%d'), v_altin, v_doviz, v_hisse, v_kripto, v_mevduat])
            if success:
                st.success("Kaydedildi! Veriler güncelleniyor...")
                time.sleep(1)
                st.rerun()

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
            f_match = df_p[df_p['Fon Kodu'] == kod] if not df_p.empty else pd.DataFrame()
            
            fiyat = 0.0
            if not f_match.empty:
                try:
                    fiyat = float(str(f_match.iloc[0]['Son Fiyat']).replace(',', '.'))
                    st.info(f"💰 Birim Fiyat: {fiyat} TL | Toplam: {lot*fiyat:,.2f} TL")
                except: pass

            if st.button("PORTFÖYE EKLE"):
                row = [datetime.now().strftime('%Y-%m-%d'), kod, ad, lot, fiyat, lot*fiyat, src]
                if write_to_sheet("Veri_Giris", row):
                    if f_match.empty:
                        write_to_sheet(p_sheet, [kod, "", 0])
                    st.success("İşlem Başarılı!")
                    time.sleep(1)
                    st.rerun()

    st.divider()
    st.subheader("Son İşlemler")
    st.dataframe(get_data_from_sheet("Veri_Giris"), use_container_width=True)
