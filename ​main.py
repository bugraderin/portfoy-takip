import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
                'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Mevcut Sekmeler
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
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
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
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_v2 = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🚀 Portföy V2"])

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
                p_in[e] = st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f", help=f"Son Değer: {int(son_val):,.0f} TL")

            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')]
                for e in enstrumanlar:
                    val = p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0))
                    yeni_satir.append(val)
                ws_portfoy.append_row(yeni_satir)
                st.success("✅ Kaydedildi!"); st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        
        guncel = df_p.iloc[-1]
        st.metric("Toplam Varlık (TL)", f"{int(guncel['Toplam']):,.0f}".replace(",", "."))

        st.write("### ⏱️ Değişim Analizi")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "1 Yıl": 365}
        sec_per = st.selectbox("Analiz Periyodu", list(periyotlar.keys()))
        
        # Grafik ve metrik bölümleri...
        fig_p_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
        st.plotly_chart(fig_p_line, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0)
        p = c2.number_input("Prim", min_value=0)
        y = c3.number_input("Yatırımlar", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y])
            st.rerun()

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    gider_ikonlari = {"Genel": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kart": "💳"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(len(gider_ikonlari))
        inputs = {isim: cols[i].number_input(f"{ikon} {isim}", min_value=0) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum([v or 0 for v in inputs.values()])
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + list(inputs.values()))
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan_bakiye - toplam_h])
            st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    kb, ml = get_son_bakiye_ve_limit()
    st.write(f"Kalan: {int(kb)} TL")
    yeni_ekle = st.number_input("Ekle", min_value=0)
    if st.button("Bakiyeye Ekle"):
        ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_ekle, kb + yeni_ekle])
        st.rerun()

# --- SEKME 5: PORTFÖY V2 (YENİ EKLEDİĞİMİZ) ---
with tab_v2:
    st.header("🚀 Portföy V2 - Akıllı Fon Takibi")
    try:
        data_f = ws_fon_listesi.get_all_records()
        df_f = pd.DataFrame(data_f)
        options = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_f.iterrows()]
        secilen = st.selectbox("Fon Seçin:", options=options, index=None)

        if secilen:
            f_kod = secilen.split(" - ")[0]
            f_ad = secilen.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            with c1:
                kaynak = st.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
                ws_fiyat = ws_tefas_fiyat if kaynak == "Tefas" else ws_befas_fiyat
            with c2:
                lot = st.number_input("Lot", min_value=0.0, step=0.01)

            # Fiyat Çekme
            f_df = pd.DataFrame(ws_fiyat.get_all_records())
            f_row = f_df[f_df['Fon Kodu'] == f_kod]
            
            if not f_row.empty:
                fiyat = float(f_row.iloc[0]['Son Fiyat'])
                tutar = lot * fiyat
                st.metric(f"Birim Fiyat ({kaynak})", f"{fiyat:.6f} TL")
                st.subheader(f"💰 Tutar: {tutar:,.2f} TL")
                if st.button("📥 Portföye Ekle"):
                    ws_veri_giris.append_row([datetime.now().strftime("%Y-%m-%d"), f_kod, f_ad, lot, fiyat, tutar, kaynak])
                    st.success("Kaydedildi!"); st.rerun()
            else:
                st.warning("Fiyat yok!")
                if st.button("Kodu Listeye Ekle"):
                    ws_fiyat.append_row([f_kod, 0])
                    st.rerun()

        st.divider()
        st.subheader("📋 Kayıtlı Fon Detayları")
        v2_df = pd.DataFrame(ws_veri_giris.get_all_records())
        st.dataframe(v2_df, use_container_width=True)
    except Exception as e:
        st.error(f"Hata: {e}")
