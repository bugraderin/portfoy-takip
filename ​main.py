import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Panel", layout="wide")

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

# --- ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY (PERFORMANS VE GELİŞİM) ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        guncel = df_p.iloc[-1]

        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        
        st.divider()
        # Performans Göstergeleri
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "9 Ay": 270, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
        secim = st.selectbox("Kıyaslama süresi:", list(periyotlar.keys()))
        
        h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
        gecmis_df = df_p[df_p['tarih'] <= h_tarih]
        baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
        
        t_fark = guncel['Toplam'] - baslangic['Toplam']
        b_yuzde = (t_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
        st.success(f"**{secim}** öncesine göre büyüme: **%{b_yuzde:.2f}**")

        # Gelişim Grafiği
        fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Varlık Gelişim Grafiği")
        st.plotly_chart(fig_line, use_container_width=True)

# --- SEKME 3: GİDERLER (DİNAMİK ETİKETLER VE DOĞRU SIRALAMA) ---
with tab_gider:
    st.subheader("💸 Harcama Girişi")
    kalan_bakiye, limit = get_son_butce_durumu()
    st.info(f"💰 Kalan Bütçeniz: **{kalan_bakiye:,.0f} TL**")
    
    with st.form("gi_form", clear_on_submit=True):
        # Üst Panel: Dinamik Seçimler
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.write("📦 **Genel**")
            g_tur = st.selectbox("Tür", ["Sigara", "Kozmetik", "Kırtasiye", "Evcil Hayvan", "Giyim", "Eğlence", "Diğer"])
            # Dinamik Etiket: Seçtiğin tür neyse kutunun ismi o olur
            g_tutar = st.number_input(f"{g_tur} Tutarı", min_value=0, value=None, format="%d")
        
        with c2:
            st.write("🚗 **Araba**")
            a_tur = st.selectbox("Tür", ["Benzin", "Bakım", "Diğer"])
            a_tutar = st.number_input(f"{a_tur} Tutarı", min_value=0, value=None, format="%d")
            
        with c3:
            st.write("🏦 **Kredi**")
            k_tur = st.selectbox("Tür", ["Banka Kredisi", "Öğrenim Kredisi", "Diğer"])
            k_tutar = st.number_input(f"{k_tur} Tutarı", min_value=0, value=None, format="%d")

        st.divider()
        st.write("🏠 **Sabit Giderler**")
        
        # Ekran görüntündeki sıralamaya göre alt panel
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

        if st.form_submit_button("✅ Kaydet ve Bütçeden Düş"):
            # GÖRSELDEKİ SÜTUN SIRALAMASI (A'dan M'ye):
            # tarih(A), Genel(B), Market(C), Kira(D), Aidat(E), KK(F), Kredi(G), Eğitim(H), Araba(I), Seyahat(J), Sağlık(K), Çocuk(L), TopluTaşıma(M)
            harcama_satiri = [
                datetime.now().strftime('%Y-%m-%d'), # A
                g_tutar or 0,                        # B (Genel)
                market or 0,                         # C (Market)
                kira or 0,                           # D (Kira)
                aidat or 0,                          # E (Aidat)
                kk or 0,                             # F (Kredi Kartı)
                k_tutar or 0,                        # G (Kredi)
                egitim or 0,                         # H (Eğitim)
                a_tutar or 0,                        # I (Araba)
                seyahat or 0,                        # J (Seyahat)
                saglik or 0,                         # K (Sağlık)
                cocuk or 0,                          # L (Çocuk)
                ulashim or 0,                        # M (Toplu Taşıma)
                f"Türler: {g_tur} | {a_tur} | {k_tur}" # N (Notlar)
            ]
            
            # 1. Giderler Sayfasına Yaz
            ws_gider.append_row(harcama_satiri, value_input_option='RAW')
            
            # 2. Bütçe Sayfasını Güncelle (Kalanı Düş)
            toplam_h = sum([x for x in harcama_satiri[1:13] if isinstance(x, (int, float))])
            yeni_kalan = kalan_bakiye - toplam_h
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan, kalan_bakiye], value_input_option='RAW')
            
            st.success(f"Başarıyla kaydedildi. Yeni bakiye: {yeni_kalan} TL")
            st.rerun()

# --- DİĞER SEKMELER (GELİR VE BÜTÇE LİMİTİ) ---
with tab_ayrilan:
    with st.form("a_f"):
        l = st.number_input("Aylık Bütçe Limiti", min_value=0)
        if st.form_submit_button("Limit Tanımla"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), l, l, 0], value_input_option='RAW')
            st.rerun()

with tab_gelir:
    with st.form("g_f"):
        m = st.number_input("Maaş", min_value=0)
        if st.form_submit_button("Gelir Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, 0, 0], value_input_option='RAW')
            st.rerun()
