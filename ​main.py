import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
# Bu komut her zaman en üstte (importlardan hemen sonra) ve tek başına olmalıdır.
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {
    'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
    'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'
}

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Standart Sekmeler
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    
    # Portföy V2 Sekmeleri
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas_fiyat = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas_fiyat = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
</style>
""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_v2 = st.tabs([
    "📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🚀 Portföy V2"
])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())
    
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        try:
            temp_data = ws_portfoy.get_all_records()
            son_kayitlar = pd.DataFrame(temp_data).iloc[-1] if temp_data else {e: 0.0 for e in enstrumanlar}
        except: son_kayitlar = {e: 0.0 for e in enstrumanlar}

        with st.form("p_form", clear_on_submit=True):
            p_in = {}
            for e in enstrumanlar:
                son_val = float(son_kayitlar.get(e, 0))
                p_in[e] = st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f")
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0)) for e in enstrumanlar]
                ws_portfoy.append_row(yeni_satir)
                st.success("✅ Kaydedildi!"); st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'])
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        st.metric("Toplam Varlık (TL)", f"{int(df_p.iloc[-1]['Toplam']):,.0f}".replace(",", "."))
        st.plotly_chart(px.line(df_p, x='tarih', y='Toplam', title="Varlık Seyri"), use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0)
        p = c2.number_input("Prim", min_value=0)
        y = c3.number_input("Yatırım", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y])
            st.success("Gelir eklendi!"); st.rerun()

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    gider_ikonlari = {"Market": "🛒", "Kira": "🏠", "Fatura": "⚡", "Kart": "💳", "Dışarıda Yemek": "🍽️"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(len(gider_ikonlari))
        inputs = {isim: cols[i].number_input(f"{ikon} {isim}", min_value=0) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum(inputs.values())
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + list(inputs.values()))
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan_bakiye - toplam_h])
            st.success("Kaydedildi!"); st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Yönetimi")
    kb, ml = get_son_bakiye_ve_limit()
    ekle = st.number_input("Eklenecek Tutar (TL)", min_value=0)
    if st.button("Bakiyeye Ekle"):
        ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), ekle, kb + ekle])
        st.success("Bakiye güncellendi!"); st.rerun()

# --- SEKME 5: PORTFÖY V2 ---
with tab_v2:
    st.header("🚀 Gelişmiş Fon Takip Sistemi")
    try:
        # Arama kutusu için fon listesini çek
        df_fonlar = pd.DataFrame(ws_fon_listesi.get_all_records())
        fon_secenekleri = [f"{row['Fon Kodu']} - {row['Fon Adı']}" for _, row in df_fonlar.iterrows()]
        
        secilen_full = st.selectbox("Fon Arayın:", options=fon_secenekleri, index=None, placeholder="Örn: VGA")

        if secilen_full:
            sec_kod = secilen_full.split(" - ")[0]
            sec_ad = secilen_full.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            with c1:
                kaynak = st.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
                ws_fiyat = ws_tefas_fiyat if kaynak == "Tefas" else ws_befas_fiyat
            with c2:
                lot = st.number_input("Lot Miktarı:", min_value=0.0, step=0.01)

            # Fiyat Kontrolü
            fiyat_df = pd.DataFrame(ws_fiyat.get_all_records())
            fon_fiyat_row = fiyat_df[fiyat_df['Fon Kodu'] == sec_kod]

            if not fon_fiyat_row.empty:
                fiyat = float(fon_fiyat_row.iloc[0]['Son Fiyat'])
                tutar = lot * fiyat
                st.metric(f"Anlık {kaynak} Fiyatı", f"{fiyat:.6f} TL")
                st.subheader(f"💰 Tutar: {tutar:,.2f} TL")
                
                if st.button("📥 Portföye Ekle"):
                    ws_veri_giris.append_row([datetime.now().strftime("%Y-%m-%d"), sec_kod, sec_ad, lot, fiyat, tutar, kaynak])
                    st.balloons(); st.success("Eklendi!"); st.rerun()
            else:
                st.warning("Bu fonun fiyatı henüz bu kaynakta yok.")
                if st.button("➕ Fiyat Listesine Ekle"):
                    ws_fiyat.append_row([sec_kod, 0])
                    st.info("Kod eklendi, fiyat bekleniyor.")

        st.divider()
        st.subheader("🗑️ Kayıtlı Fonlarım")
        v2_data = ws_veri_giris.get_all_records()
        if v2_data:
            df_v2 = pd.DataFrame(v2_data)
            st.dataframe(df_v2, use_container_width=True)
            
            silinecek = st.selectbox("Silinecek Fonu Seçin:", df_v2['Kod'].unique())
            if st.button("Seçili Fonu Sil"):
                cell = ws_veri_giris.find(silinecek)
                ws_veri_giris.delete_rows(cell.row)
                st.success("Silindi!"); st.rerun()
    except Exception as e:
        st.error(f"V2 Hatası: {e}")
