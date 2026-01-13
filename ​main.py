import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Yönetim Merkezi", layout="wide")
st.title("🚀 Akıllı Portföy ve Bütçe Yönetimi")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# CSS: Artı/Eksi oklarını gizleme
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYON: BÜTÇE HESAPLAMA ---
def get_son_butce_durumu():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            return float(data[-1]['Kalan']), float(data[-1]['Ayrılan Tutar'])
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- 2. ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY (TÜM SÜRELER EKLENDİ) ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    # Yan Menüden Veri Girişi
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("Kaydet"):
                ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar], value_input_option='RAW')
                st.rerun()

    # Veri İşleme
    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        guncel = df_p.iloc[-1]

        # Üst Özet
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        if len(df_p) > 1:
            deg = guncel['Toplam'] - df_p['Toplam'].iloc[-2]
            y_deg = (deg / df_p['Toplam'].iloc[-2]) * 100
            c2.metric("Günlük Değişim", f"{deg:,.0f} TL", f"%{y_deg:.2f}")
        
        # PERFORMANS ANALİZİ (İSTEDİĞİN TÜM SÜRELER)
        st.divider()
        st.subheader("⏱️ Dönemsel Performans")
        # 1 gün, 1-3-6-9 ay, 1-3-5 yıl
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "9 Ay": 270, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
        secim = st.selectbox("Kıyaslama süresi:", list(periyotlar.keys()))
        
        h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
        gecmis_df = df_p[df_p['tarih'] <= h_tarih]
        baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
        
        t_fark = guncel['Toplam'] - baslangic['Toplam']
        b_yuzde = (t_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
        st.success(f"**{secim}** öncesine göre büyüme: **%{b_yuzde:.2f}** ({t_fark:,.0f} TL fark)")

        # Grafikler
        t_da, t_ge = st.tabs(["🥧 Dağılım", "📈 Gelişim"])
        with t_da:
            plot_df = pd.DataFrame([{'V': f"{enstruman_bilgi[e]} {e}", 'D': guncel[e]} for e in enstrumanlar if guncel[e] > 0]).sort_values('D', ascending=False)
            fig = px.pie(plot_df, values='D', names='V', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    gelir_k = ["Maaş", "Prim&Promosyon", "Yatırımlar"]
    with st.form("g_form", clear_on_submit=True):
        g_in = {k: st.number_input(f"{k} (TL)", min_value=0, value=None, format="%d") for k in gelir_k}
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d')] + [g_in[k] or 0 for k in gelir_k], value_input_option='RAW')
            st.success("Kaydedildi!")

# --- SEKME 3: GİDERLER (BÜTÇEDEN DÜŞER) ---
with tab_gider:
    st.subheader("💸 Gider Girişi")
    kalan, limit = get_son_butce_durumu()
    st.info(f"💰 Kalan Bütçeniz: **{kalan:,.0f} TL** / (Limit: {limit:,.0f} TL)")
    
    gider_k = ["Genel Giderler", "Market", "Kira", "Aidat", "Kredi Kartı", "Kredi", "Eğitim", "Araba", "Seyahat", "Sağlık", "Çocuk", "Toplu Taşıma"]
    with st.form("gi_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        gi_in = {k: (c1 if i<6 else c2).number_input(f"{k} (TL)", min_value=0, value=None, format="%d") for i, k in enumerate(gider_k)}
        if st.form_submit_button("Harcamayı Bütçeden Düş"):
            toplam_h = sum([gi_in[k] or 0 for k in gider_k])
            yeni_kalan = kalan - toplam_h
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [gi_in[k] or 0 for k in gider_k], value_input_option='RAW')
            # Bütçe sayfasını güncelle
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan, kalan], value_input_option='RAW')
            st.success(f"Harcama kaydedildi. Kalan: {yeni_kalan} TL")
            st.rerun()

# --- SEKME 4: BÜTÇE PLANLAMA ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Belirle")
    with st.form("a_form", clear_on_submit=True):
        y_lim = st.number_input("Aylık Limit (Ayrılan Tutar)", min_value=0, value=None, format="%d")
        dev = st.number_input("Devreden Tutar", min_value=0, value=None, format="%d")
        if st.form_submit_button("Limiti Başlat"):
            total = (y_lim or 0) + (dev or 0)
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), y_lim or 0, total, dev or 0], value_input_option='RAW')
            st.success(f"Bütçe başlatıldı: {total} TL")
            st.rerun()
