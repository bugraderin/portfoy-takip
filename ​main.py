import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- 1. AYARLAR & BAĞLANTI (KOTA DOSTU) ---
st.set_page_config(page_title="Portfoy Takip", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    spreadsheet = client.open("portfoyum")
    
    # GÖRSELİNDEKİ SAYFA İSİMLERİ
    ws_v_miktar = spreadsheet.worksheet("Varlik_Miktarlari")
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası (Sayfa İsimlerini Kontrol Et): {e}")
    st.stop()

def get_data(ws):
    """Kota aşımını önlemek için veriyi güvenli çeker"""
    try:
        time.sleep(0.3) 
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = [c.strip() for c in df.columns]
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 2. SEKMELER ---
tab_ana, tab_fon_v2 = st.tabs(["📊 Genel Durum & Manuel Giriş", "🚀 Portföy V2 (Fon)"])

# --- SEKME 1: GENEL DURUM (Varlik_Miktarlari Sayfası) ---
with tab_ana:
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        st.subheader("📥 Varlık Miktarlarını Güncelle")
        # Bu form Varlik_Miktarlari sayfasına yazar
        with st.form("varlik_form", clear_on_submit=True):
            f_altin = st.number_input("Altın", min_value=0.0)
            f_doviz = st.number_input("Döviz", min_value=0.0)
            f_hisse = st.number_input("Hisse Senedi", min_value=0.0)
            f_kripto = st.number_input("Kripto", min_value=0.0)
            f_mevduat = st.number_input("Mevduat", min_value=0.0)
            
            submit_v = st.form_submit_button("Varlıkları Kaydet")
            if submit_v:
                # Veriyi Varlik_Miktarlari sayfasına ekler
                ws_v_miktar.append_row([datetime.now().strftime('%Y-%m-%d'), f_altin, f_doviz, f_hisse, f_kripto, f_mevduat])
                st.success("Varlik_Miktarlari sayfasına eklendi!")
                st.rerun()

    with col_r:
        st.subheader("📈 Güncel Varlık Durumu")
        df_m = get_data(ws_v_miktar)
        if not df_m.empty:
            last = df_m.iloc[-1].copy()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Altın", f"{last.get('Altin', '0')}")
            m2.metric("Döviz", f"{last.get('Doviz', '0')}")
            m3.metric("Hisse", f"{last.get('HisseSenedi', '0')}")
            m4.metric("Kripto", f"{last.get('Kripto', '0')}")
            
            # Grafik
            df_m['tarih'] = pd.to_datetime(df_m.iloc[:, 0], errors='coerce')
            st.plotly_chart(px.line(df_m, x='tarih', y=df_m.columns[1:], title="Varlık Seyri"), use_container_width=True)

# --- SEKME 2: PORTFÖY V2 (Veri_Giris Sayfası) ---
with tab_fon_v2:
    st.subheader("🎯 Detaylı Fon Girişi")
    df_list = get_data(ws_fon_listesi)
    
    if not df_list.empty:
        f_names = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_list.iterrows()]
        sec_fon = st.selectbox("Fon Seç:", options=f_names, index=None)
        
        if sec_fon:
            f_kod = sec_fon.split(" - ")[0]
            f_ad = sec_fon.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            f_lot = c2.number_input("Lot Miktarı:", min_value=0.0, step=0.1)
            
            # İlgili fiyat sayfasını oku
            ws_price = ws_tefas if src == "Tefas" else ws_befas
            df_price = get_data(ws_price)
            
            f_match = df_price[df_price['Fon Kodu'] == f_kod] if not df_price.empty else pd.DataFrame()
            
            if not f_match.empty:
                try:
                    price_val = float(str(f_match.iloc[0]['Son Fiyat']).replace(',', '.'))
                    total_val = f_lot * price_val
                    st.info(f"💡 Birim Fiyat: {price_val} TL | Toplam: {total_val:,.2f} TL")
                    
                    # KAYIT BUTONU
                    if st.button("📥 Fonu Veri_Giris'e Kaydet", use_container_width=True):
                        ws_veri_giris.append_row([datetime.now().strftime('%Y-%m-%d'), f_kod, f_ad, f_lot, price_val, total_val, src])
                        st.success("Fon Veri_Giris sayfasına başarıyla eklendi!")
                        st.rerun()
                except:
                    st.error("Fiyat sayıya dönüştürülemedi!")
            else:
                st.warning(f"Bu fonun fiyatı {src} listesinde bulunamadı.")
    
    st.divider()
    st.write("📋 **Son Fon İşlemleri (Veri_Giris Sayfası)**")
    st.dataframe(get_data(ws_veri_giris), use_container_width=True)
