import yfinance as yf
import requests
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from tefas import Crawler
tefas_crawler = Crawler()

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
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    ws_lotlar = spreadsheet.worksheet("Lotlar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- ANALİZ VE VERİ FONKSİYONLARI ---

def get_tefas_analiz(kod):
    try:
        # Google Sheets'ten verileri çekiyoruz
        data = ws_lotlar.get_all_records()
        df_sheets = pd.DataFrame(data)
        
        # 'Kod' sütununda seçilen fonu buluyoruz
        satir = df_sheets[df_sheets['Kod'] == kod]
        
        if not satir.empty:
            # Sheets'teki 'GuncelFiyat' sütunundaki değeri al
            fiyat = satir.iloc[-1]['GuncelFiyat']
            # Sayıya çeviriyoruz
            fiyat_float = float(str(fiyat).replace(",", "."))
            return pd.DataFrame([{'date': datetime.now(), 'price': fiyat_float}])
        return None
    except Exception as e:
        return None
      
def get_periyodik_getiri(df):
    if df is None: return {}
    son_fiyat = df.iloc[-1]['price']
    periyotlar = {"1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
    getiriler = {}
    for etiket, gun in periyotlar.items():
        hedef_tarih = df.iloc[-1]['date'] - timedelta(days=gun)
        gecmis_df = df[df['date'] <= hedef_tarih]
        if not gecmis_df.empty:
            esk_fiyat = gecmis_df.iloc[-1]['price']
            getiriler[etiket] = ((son_fiyat - esk_fiyat) / esk_fiyat) * 100
        else:
            getiriler[etiket] = None
    return getiriler

@st.cache_data(ttl=3600)
def get_hisse_fiyat(kod):
    try:
        tckr = yf.Ticker(f"{kod}.IS")
        return tckr.fast_info['last_price']
    except:
        return None

# CSS Düzenlemeleri
st.markdown("""<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    </style>""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_canli = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🌐 Canlı Veri & TEFAS"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar], value_input_option='RAW')
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        
        guncel = df_p.iloc[-1]
        toplam_tl = guncel['Toplam']

        st.metric("Toplam Varlık (TL)", f"{int(toplam_tl):,.0f}".replace(",", "."))

        st.write("### ⏱️ Değişim Analizi")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
        secilen_periyot = st.selectbox("Analiz Periyodu Seçin", list(periyotlar.keys()))
        
        gun_farki = periyotlar[secilen_periyot]
        hedef_tarih = guncel['tarih'] - timedelta(days=gun_farki)
        
        gecmis_data = df_p[df_p['tarih'] <= hedef_tarih]
        if gecmis_data.empty and len(df_p) > 1:
            gecmis_data = df_p.head(1)
            st.caption(f"ℹ️ En eski kayıt ({gecmis_data.iloc[0]['tarih'].strftime('%d.%m.%Y')}) baz alındı.")
        
        if not gecmis_data.empty and len(df_p) > 1:
            eski_deger = gecmis_data.iloc[-1]['Toplam']
            if eski_deger > 0:
                fark = toplam_tl - eski_deger
                yuzde = (fark / eski_deger) * 100
                st.metric(f"{secilen_periyot} Değişimi", f"{int(fark):,.0f} TL".replace(",", "."), f"%{yuzde:.2f}")

        st.divider()
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_data.append({'Cins': e, 'Tutar': guncel[e], 'Yüzde': yuzde, 'Icon': enstruman_bilgi[e]})
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols = st.columns(4)
        for i, (index, row) in enumerate(df_v.iterrows()):
            with cols[i % 4]:
                st.metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), f"%{row['Yüzde']:.2f}")

        st.divider()
        sub_tab1, sub_tab2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        with sub_tab1:
            df_v['Etiket'] = df_v['Icon'] + " " + df_v['Cins']
            fig_p = px.pie(df_v, values='Tutar', names='Etiket', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
        with sub_tab2:
            df_p['tarih_tr'] = df_p['tarih'].dt.day.astype(str) + " " + df_p['tarih'].dt.month.map(TR_AYLAR_TAM)
            fig_l = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
            st.plotly_chart(fig_l, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None)
        p = c2.number_input("Prim & Promosyon", min_value=0, value=None)
        y = c3.number_input("Yatırımlar", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam], value_input_option='RAW')
            st.success("Kaydedildi."); st.rerun()

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f}**")
    gider_ikonlari = {"Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kredi Kartı": "💳", "Kredi": "🏦", "Eğitim": "🎓", "Araba": "🚗", "Seyahat": "✈️", "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(3)
        inputs = {isim: cols[i % 3].number_input(f"{ikon} {isim}", min_value=0, value=None) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum([v or 0 for v in inputs.values()])
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [inputs[k] or 0 for k in gider_ikonlari.keys()], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                st.success(f"Kaydedildi. Kalan: {int(yeni_kalan)}"); st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    with st.form("b_form"):
        yeni_l = st.number_input("Yeni Aylık Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_l, yeni_l], value_input_option='RAW')
            st.success("Bütçe güncellendi."); st.rerun()

# --- SEKME 5: CANLI VERİ & TEFAS İÇERİĞİ ---
with tab_canli:
    st.subheader("🌐 Canlı Piyasa ve Fon Analizi")
    
    # ... (Yeni Lot Ekleme formu aynı kalsın) ...

    st.divider()
    secilen_kod = st.text_input("🔍 Fon Analizi (Örn: GMR, TI3, AFT)", value="AFT").upper()
    
    if secilen_kod:
        with st.spinner("Veriler çekiliyor..."):
            fon_data = get_tefas_analiz(secilen_kod)
            
            if fon_data is not None and not fon_data.empty:
                # Güncel Fiyatı Büyükçe Gösterelim
                guncel_fiyat = fon_data.iloc[-1]['price']
                st.metric(f"{secilen_kod} Güncel Fiyat", f"{guncel_fiyat:,.4f} TL")
                
                # Eğer veri sadece 1 satırsa (Mynet'ten gelen durum)
                if len(fon_data) == 1:
                    st.info("ℹ️ TEFAS engeli nedeniyle geçmiş veriler ve grafik şu an gösterilemiyor, ancak güncel fiyat başarıyla çekildi.")
                else:
                    # Eğer bir şekilde geçmiş veri gelirse (TEFAS çalışırsa) grafiği çiz
                    getiriler = get_periyodik_getiri(fon_data)
                    m_cols = st.columns(len(getiriler))
                    for i, (label, val) in enumerate(getiriler.items()):
                        with m_cols[i]:
                            if val is not None:
                                st.metric(label, f"%{val:.2f}")
                    
                    fig_fon = px.line(fon_data, x='date', y='price', title=f"{secilen_kod} Fiyat Seyri")
                    st.plotly_chart(fig_fon, use_container_width=True)
            else:
                st.warning("⚠️ Veri çekilemedi. Mynet veya TEFAS şu an yanıt vermiyor.")
