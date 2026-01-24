import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")

@st.cache_resource
def get_gc():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def get_data_cached(sheet_name):
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
        st.error(f"{sheet_name} okunamadı: {e}")
        return pd.DataFrame()

def write_to_sheet(sheet_name, row):
    gc = get_gc()
    sh = gc.open("portfoyum")
    ws = sh.worksheet(sheet_name)
    ws.append_row(row)
    st.cache_data.clear()

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

with tab_ana:
    st.subheader("Varlık Güncelleme")
    # Varlık giriş formu (Varlik_Miktarlari sayfasına yazar)
    with st.form("v_form"):
        c1, c2, c3, c4, c5 = st.columns(5)
        v_altin = c1.number_input("Altın", min_value=0.0)
        v_doviz = c2.number_input("Döviz", min_value=0.0)
        v_hisse = c3.number_input("Hisse", min_value=0.0)
        v_kripto = c4.number_input("Kripto", min_value=0.0)
        v_mevduat = c5.number_input("Mevduat", min_value=0.0)
        
        if st.form_submit_button("Varlıkları Kaydet"):
            write_to_sheet("Varlik_Miktarlari", [datetime.now().strftime('%d.%m.%Y'), v_altin, v_doviz, v_hisse, v_kripto, v_mevduat])
            st.success("Varlıklar kaydedildi!")
            st.rerun()

with tab_fon_v2:
    st.subheader("Fon Portföy Girişi")
    df_l = get_data_cached("Fon_Listesi")
    
    if not df_l.empty:
        # Başlık isimlerinin 'Fon Kodu' ve 'Fon Adı' olduğundan emin olun
        f_opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        sec_f = st.selectbox("Fon Seçiniz:", options=f_opts, index=None)
        
        if sec_f:
            kod = sec_f.split(" - ")[0].strip()
            ad = sec_f.split(" - ")[1].strip()
            
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            lot = c2.number_input("Lot Miktarı:", min_value=0.0, step=0.01)
            
            # --- YENİ YATAY YAPIYA GÖRE FİYAT ÇEKME ---
            p_sheet = "TefasFonVerileri" if src == "Tefas" else "BefasFonVerileri"
            df_p = get_data_cached(p_sheet)
            
            fiyat = 0.0
            # HATA BURADAYDI: Artık 'Fon Kodu' diye bir sütun yok, Kodlar başlığın kendisi!
            if not df_p.empty and kod in df_p.columns:
                # En son satırdaki (güncel) fiyatı al
                raw_price = str(df_p[kod].iloc[-1]).strip().replace(',', '.')
                try:
                    fiyat = float(raw_price) if raw_price else 0.0
                except: fiyat = 0.0
                
                if fiyat > 0:
                    st.info(f"💡 {kod} Güncel Fiyatı: {fiyat} TL | Toplam: {lot*fiyat:,.2f} TL")
                else:
                    st.warning("⚠️ Fiyat 0 görünüyor, Apps Script güncelleyecektir.")
            else:
                st.warning(f"⚠️ {kod} kodu henüz {p_sheet} sayfasında sütun olarak açılmamış.")

            if st.button("PORTFÖYE EKLE"):
                # Apps Script'in beklediği Veri_Giris başlıkları: 
                # Tarih, Kod, Ad, Lot, Fiyat, Toplam, Kaynak
                tarih_str = datetime.now().strftime('%d.%m.%Y')
                row = [tarih_str, kod, ad, lot, fiyat, lot*fiyat, src]
                
                write_to_sheet("Veri_Giris", row)
                st.success(f"{kod} başarıyla eklendi!")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("Son İşlemler")
    st.dataframe(get_data_cached("Veri_Giris"), use_container_width=True)
