import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI ---
st.set_page_config(page_title="Finansal Portföy Yönetimi", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    spreadsheet = client.open("portfoyum")
    
    # Tanımladığın Sayfa İsimleri
    ws_v_miktar = spreadsheet.worksheet("Varlik_Miktarlari")
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas = spreadsheet.worksheet("BefasFonVerileri")
    
    # Detay Sayfaları (Gelecekteki işlemler için hazır)
    ws_altin = spreadsheet.worksheet("Altin")
    ws_doviz = spreadsheet.worksheet("Doviz")
    ws_hisse = spreadsheet.worksheet("HisseSenedi")
    ws_mevduat = spreadsheet.worksheet("Mevduat")
    ws_kripto = spreadsheet.worksheet("Kripto")
    
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

def get_data(ws):
    try:
        time.sleep(0.3) # API Kotasını korumak için
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = [c.strip() for c in df.columns]
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum", "🚀 Portföy V2"])

# --- SEKME 1: VARLIK MİKTARLARI ---
with tab_ana:
    st.subheader("Varlık Güncelleme")
    with st.form("v_form"):
        c1, c2, c3, c4, c5 = st.columns(5)
        v_altin = c1.number_input("Altın", min_value=0.0)
        v_doviz = c2.number_input("Döviz", min_value=0.0)
        v_hisse = c3.number_input("Hisse", min_value=0.0)
        v_kripto = c4.number_input("Kripto", min_value=0.0)
        v_mevduat = c5.number_input("Mevduat", min_value=0.0)
        
        if st.form_submit_button("Verileri Kaydet"):
            ws_v_miktar.append_row([datetime.now().strftime('%Y-%m-%d'), v_altin, v_doviz, v_hisse, v_kripto, v_mevduat])
            st.success("Varlıklar Varlik_Miktarlari sayfasına kaydedildi.")
            st.rerun()

# --- SEKME 2: PORTFÖY V2 (FON KAYIT) ---
with tab_fon_v2:
    st.subheader("Fon Portföy Girişi")
    
    df_l = get_data(ws_fon_listesi)
    if not df_l.empty:
        f_opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_l.iterrows()]
        sec_f = st.selectbox("Fon Seçimi:", options=f_opts, index=None)
        
        if sec_f:
            kod = sec_f.split(" - ")[0]
            ad = sec_f.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            lot = c2.number_input("Lot Miktarı:", min_value=0.0, step=0.01)
            
            ws_price_target = ws_tefas if src == "Tefas" else ws_befas
            df_p = get_data(ws_price_target)
            f_match = df_p[df_p['Fon Kodu'] == kod] if not df_p.empty else pd.DataFrame()
            
            # --- Hata Alınan Bölüm (Tamir Edildi) ---
            fiyat = 0.0
            if not f_match.empty:
                raw_price = str(f_match.iloc[0]['Son Fiyat']).strip().replace(',', '.')
                # Sayı kontrolü: Boş değilse ve geçerli formatta ise float'a çevir
                try:
                    if raw_price:
                        fiyat = float(raw_price)
                        st.info(f"💡 Güncel {src} Fiyatı: {fiyat} TL | Toplam Değer: {lot*fiyat:,.2f} TL")
                    else:
                        st.warning(f"⚠️ {kod} için fiyat hücresi boş. 0.0 kabul edildi.")
                except ValueError:
                    st.error(f"⚠️ '{raw_price}' değeri sayıya çevrilemiyor! Lütfen {src} sayfasını kontrol et.")
            else:
                st.warning(f"Fiyat bulunamadı. Kaydedince {src} listesine eklenecek.")

            if st.button("KAYDET", use_container_width=True):
                # 1. Veri_Giris sayfasına kayıt
                ws_veri_giris.append_row([
                    datetime.now().strftime('%Y-%m-%d'), 
                    kod, ad, lot, fiyat, lot*fiyat, src
                ])
                
                # 2. Fiyat listesinde yoksa kodu ekle
                if f_match.empty:
                    ws_price_target.append_row([kod, 0])
                
                st.success(f"{kod} başarıyla kaydedildi.")
                time.sleep(1)
                st.rerun()

    st.divider()
    st.subheader("Veri_Giris Kayıtları")
    df_history = get_data(ws_veri_giris)
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
