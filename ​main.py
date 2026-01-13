import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy ve Gider Yönetimi", layout="wide")
st.title("🚀 Akıllı Finansal Yönetim Paneli")

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

# CSS: Artı/Eksi butonlarını gizler
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def get_son_butce_durumu():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son['Kalan']), float(son['Ayrılan Tutar'])
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- 2. ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY (TÜM FONKSİYONLAR GERİ GELDİ) ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    # YAN MENÜ: PORTFÖY GİRİŞİ
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("🚀 Portföyü Kaydet"):
                ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar], value_input_option='RAW')
                st.success("Portföy güncellendi!")
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        guncel = df_p.iloc[-1]

        # Özet Metrikler
        c1, c2 = st.columns(2)
        c1.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        
        if len(df_p) > 1:
            degisim = guncel['Toplam'] - df_p['Toplam'].iloc[-2]
            yuzde = (degisim / df_p['Toplam'].iloc[-2]) * 100
            c2.metric("Günlük Değişim", f"{degisim:,.0f} TL", f"%{yuzde:.2f}")

        st.divider()
        # Dönemsel Performans Göstergeleri (1 Gün - 5 Yıl)
        st.subheader("⏱️ Performans Analizi")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "9 Ay": 270, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
        secim = st.selectbox("Kıyaslama süresi seçin:", list(periyotlar.keys()))
        
        h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
        gecmis_df = df_p[df_p['tarih'] <= h_tarih]
        baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
        
        t_fark = guncel['Toplam'] - baslangic['Toplam']
        b_yuzde = (t_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
        st.info(f"**{secim}** öncesine göre büyüme oranı: **%{b_yuzde:.2f}**")

        # Grafik Sekmeleri
        g_tab1, g_tab2 = st.tabs(["📈 Gelişim Grafiği", "🥧 Varlık Dağılımı"])
        with g_tab1:
            fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Varlık Gelişimi (Zaman Serisi)")
            st.plotly_chart(fig_line, use_container_width=True)
        with g_tab2:
            plot_df = pd.DataFrame([{'V': f"{enstruman_bilgi[e]} {e}", 'D': guncel[e]} for e in enstrumanlar if guncel[e] > 0])
            fig_pie = px.pie(plot_df, values='D', names='V', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

# --- SEKME 3: GİDERLER (DİNAMİK ETİKETLER VE DOĞRU SIRALAMA) ---
with tab_gider:
    st.subheader("💸 Harcama Girişi")
    kalan_bakiye, limit = get_son_butce_durumu()
    st.warning(f"📉 Güncel Bütçe Bakiyesi: **{kalan_bakiye:,.0f} TL** (Tanımlı Limit: {limit:,.0f} TL)")
    
    with st.form("gi_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            g_tur = st.selectbox("Genel Gider Türü", ["Sigara", "Kozmetik", "Kırtasiye", "Evcil Hayvan", "Giyim", "Eğlence", "Diğer"])
            g_tutar = st.number_input(f"{g_tur} Tutarı", min_value=0, value=None, format="%d")
        with c2:
            a_tur = st.selectbox("Araba Gider Türü", ["Benzin", "Bakım", "Diğer"])
            a_tutar = st.number_input(f"{a_tur} Tutarı", min_value=0, value=None, format="%d")
        with c3:
            k_tur = st.selectbox("Kredi Türü", ["Banka Kredisi", "Öğrenim Kredisi", "Diğer"])
            k_tutar = st.number_input(f"{k_tur} Tutarı", min_value=0, value=None, format="%d")

        st.divider()
        st.write("🏠 **Sabit ve Diğer Harcamalar**")
        c4, c5, c6, c7 = st.columns(4)
        market = c4.number_input("Market", min_value=0, value=None)
        kira = c5.number_input("Kira", min_value=0, value=None)
        aidat = c6.number_input("Aidat", min_value=0, value=None)
        kk = c7.number_input("Kredi Kartı", min_value=0, value=None)
        
        c8, c9, c10, c11 = st.columns(4)
        egitim = c8.number_input("Eğitim", min_value=0, value=None)
        seyahat = c9.number_input("Seyahat", min_value=0, value=None)
        saglik = c10.number_input("Sağlık", min_value=0, value=None)
        cocuk = c11.number_input("Çocuk", min_value=0, value=None)
        
        ulashim = st.number_input("Toplu Taşıma", min_value=0, value=None)

        if st.form_submit_button("✅ Harcamayı Kaydet ve Bakiyeden Düş"):
            # Google Sheets Sütun Sıralaması (A-M)
            harcama_satiri = [
                datetime.now().strftime('%Y-%m-%d'), # A: tarih
                g_tutar or 0,                        # B: Genel Giderler
                market or 0,                         # C: Market
                kira or 0,                           # D: Kira
                aidat or 0,                          # E: Aidat
                kk or 0,                             # F: Kredi Kartı
                k_tutar or 0,                        # G: Kredi
                egitim or 0,                         # H: Eğitim
                a_tutar or 0,                        # I: Araba
                seyahat or 0,                        # J: Seyahat
                saglik or 0,                         # K: Sağlık
                cocuk or 0,                          # L: Çocuk
                ulashim or 0,                        # M: Toplu Taşıma
                f"Not: {g_tur}, {a_tur}, {k_tur}"    # N: Açıklama
            ]
            
            ws_gider.append_row(harcama_satiri, value_input_option='RAW')
            
            # Bütçe Sayfası Güncelleme
            toplam_h = sum([x for x in harcama_satiri[1:13] if isinstance(x, (int, float))])
            yeni_kalan = kalan_bakiye - toplam_h
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan, kalan_bakiye], value_input_option='RAW')
            
            st.success(f"İşlem başarılı! Kalan bakiye: {yeni_kalan} TL")
            st.rerun()

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    with st.form("gelir_f", clear_on_submit=True):
        m = st.number_input("Maaş", min_value=0)
        p = st.number_input("Prim", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0], value_input_option='RAW')
            st.success("Gelir kaydedildi.")

# --- SEKME 4: BÜTÇE PLANI ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Tanımlama")
    with st.form("limit_f", clear_on_submit=True):
        y_limit = st.number_input("Yeni Aylık Limit (Ayrılan Tutar)", min_value=0)
        if st.form_submit_button("Bütçeyi Başlat"):
            # [tarih, Ayrılan Tutar, Kalan, Devreden]
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), y_limit, y_limit, 0], value_input_option='RAW')
            st.success("Yeni bütçe dönemi başlatıldı!")
            st.rerun()
