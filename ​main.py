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

# Veri_Giris için cache süresini 10 saniyeye indiriyoruz ki güncellemeler anlık gelsin
@st.cache_data(ttl=10) 
def get_live_data(sheet_name):
    try:
        gc = get_gc()
        sh = gc.open("portfoyum")
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) > 0:
            headers = [str(h).strip() for h in data[0]]
            return pd.DataFrame(data[1:], columns=headers)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# Sabit listeler (Fon_Listesi vb.) için 5 dakika cache devam edebilir
@st.cache_data(ttl=300)
def get_static_data(sheet_name):
    return get_live_data(sheet_name) 

def write_to_sheet(sheet_name, row):
    gc = get_gc()
    sh = gc.open("portfoyum")
    ws = sh.worksheet(sheet_name)
    ws.append_row(row)
    st.cache_data.clear() # Tüm cache'i temizle ki yeni veri anında görünsün

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

with tab_fon_v2:
    st.subheader("🚀 Detaylı Fon Alımı")
    
    # 1. Verileri tazele butonu (Opsiyonel ama hayat kurtarır)
    if st.button("🔄 Verileri Yenile / Fiyatları Kontrol Et"):
        st.cache_data.clear()
        st.rerun()

    df_l = get_static_data("Fon_Listesi")
    
    if not df_l.empty:
        f_opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        sec_f = st.selectbox("Fon Seç:", options=f_opts, index=None)
        
        if sec_f:
            kod = sec_f.split(" - ")[0].strip()
            ad = sec_f.split(" - ")[1].strip()
            
            c1, c2 = st.columns(2)
            src = c1.radio("Kaynak:", ["Tefas", "Befas"], horizontal=True)
            lot = c2.number_input("Lot:", min_value=0.0, step=1.0, format="%.2f")
            
            # Güncel fiyatı kontrol et
            p_sheet = "TefasFonVerileri" if src == "Tefas" else "BefasFonVerileri"
            df_p = get_live_data(p_sheet)
            
            fiyat = 0.0
            if not df_p.empty and kod in df_p.columns:
                try:
                    # En son satırdaki fiyatı al
                    raw_val = str(df_p[kod].iloc[-1]).replace(',', '.')
                    fiyat = float(raw_val)
                except: fiyat = 0.0

            if fiyat > 0:
                st.success(f"✅ Güncel Fiyat: {fiyat} TL | Toplam Değer: {lot*fiyat:,.2f} TL")
            else:
                st.info("ℹ️ Bu fonun fiyatı henüz sistemde yok. Kayıt sonrası Apps Script tarafından güncellenecektir.")

            if st.button("KAYDET", use_container_width=True):
                # Apps Script'in beklediği formatta yaz
                tarih_str = datetime.now().strftime('%d.%m.%Y')
                row = [tarih_str, kod, ad, lot, fiyat, lot*fiyat, src]
                write_to_sheet("Veri_Giris", row)
                st.balloons()
                st.rerun()

    st.divider()
    st.markdown("### 📋 Son Fon İşlemleri (Veri_Giris)")
    # Burada her zaman canlı veriyi gösteriyoruz
    df_history = get_live_data("Veri_Giris")
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
