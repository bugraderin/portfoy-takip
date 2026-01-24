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

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # SENİN SAYFALARIN
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    
    # YENİ EKLENEN FON SAYFALARI
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas_fiyat = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas_fiyat = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# HATA ÖNLEYİCİ VERİ ÇEKME FONKSİYONU
def safe_get_data(ws):
    try:
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip()
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
</style>
""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    df = safe_get_data(ws_ayrilan)
    if not df.empty:
        try:
            son = df.iloc[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        except: return 0.0, 0.0
    return 0.0, 0.0

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_v2 = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🚀 Portföy V2"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        df_side = safe_get_data(ws_portfoy)
        son_kayitlar = df_side.iloc[-1] if not df_side.empty else {e: 0.0 for e in enstrumanlar}

        with st.form("p_form", clear_on_submit=True):
            p_in = {}
            for e in enstrumanlar:
                try: son_val = float(son_kayitlar.get(e, 0))
                except: son_val = 0.0
                p_in[e] = st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f", help=f"Son: {int(son_val)}")

            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')]
                for e in enstrumanlar:
                    val = p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0))
                    yeni_satir.append(val)
                ws_portfoy.append_row(yeni_satir)
                st.success("✅ Kaydedildi!"); st.rerun()

    df_p = safe_get_data(ws_portfoy)
    if not df_p.empty:
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        
        guncel = df_p.iloc[-1]
        st.metric("Toplam Varlık (TL)", f"{int(guncel['Toplam']):,.0f}")
        st.plotly_chart(px.line(df_p, x='tarih', y='Toplam', markers=True), use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3); m = c1.number_input("Maaş"); p = c2.number_input("Prim"); y = c3.number_input("Yatırım")
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y])
            st.rerun()

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    gider_ikonlari = {"Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kredi Kartı": "💳", "Kredi": "🏦", "Eğitim": "🎓", "Araba": "🚗", "Seyahat": "✈️", "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(3)
        inputs = {isim: cols[i % 3].number_input(f"{ikon} {isim}", min_value=0, value=None) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum([v or 0 for v in inputs.values()])
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [inputs[k] or 0 for k in gider_ikonlari.keys()])
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan_bakiye - toplam_h])
            st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Ekleme")
    kb, _ = get_son_bakiye_ve_limit()
    yeni = st.number_input("Eklenecek Tutar", min_value=0)
    if st.button("Bakiyeye Ekle"):
        ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni, kb + yeni])
        st.rerun()

# --- SEKME 5: PORTFÖY V2 (DETAYLI FON) ---
with tab_v2:
    st.header("🚀 Portföy V2 - Akıllı Fon Takibi")
    df_fon_listesi = safe_get_data(ws_fon_listesi)
    if not df_fon_listesi.empty:
        opts = [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_fon_listesi.iterrows()]
        sec = st.selectbox("Fon Arayın:", options=opts, index=None)
        if sec:
            kod, ad = sec.split(" - ")[0], sec.split(" - ")[1]
            c1, c2 = st.columns(2)
            src = c1.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
            lot = c2.number_input("Lot Miktarı:", min_value=0.0, step=0.01)
            ws_f = ws_tefas_fiyat if src == "Tefas" else ws_befas_fiyat
            f_df = safe_get_data(ws_f)
            f_row = f_df[f_df['Fon Kodu'] == kod] if not f_df.empty else pd.DataFrame()
            if not f_row.empty:
                fiyat = float(f_row.iloc[0]['Son Fiyat'])
                st.metric(f"{src} Fiyatı", f"{fiyat:.6f} TL", delta=f"Toplam: {lot*fiyat:,.2f} TL")
                if st.button("📥 Portföye Ekle"):
                    ws_veri_giris.append_row([datetime.now().strftime("%Y-%m-%d"), kod, ad, lot, fiyat, lot*fiyat, src])
                    st.success("Eklendi!"); st.rerun()
            else:
                st.warning("Fiyat yok!")
                if st.button("Kodu Listeye Ekle"): ws_f.append_row([kod, 0]); st.rerun()
    st.divider()
    df_v2 = safe_get_data(ws_veri_giris)
    if not df_v2.empty:
        st.dataframe(df_v2, use_container_width=True)
        sil = st.selectbox("Silinecek Fon:", df_v2['Kod'].unique())
        if st.button("Seçili Kaydı Sil"):
            cell = ws_veri_giris.find(sil)
            ws_veri_giris.delete_rows(cell.row); st.rerun()
