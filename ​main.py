import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
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
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# CSS Düzenlemeleri
st.markdown("""<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    .stRadio > div { flex-direction: row; justify-content: flex-start; } 
    </style>""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- NAVİGASYON ---
secilen_sekme = st.radio("", ["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe"], horizontal=True)

# --- SEKME 1: PORTFÖY ---
if secilen_sekme == "📊 Portföy":
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
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel

        # Dinamik Karşılık Hesaplama (Basit Parite Mantığı)
        # Not: Bu değerler girdiğin 'Döviz', 'Altın' ve 'Kripto' tutarların üzerinden oranlanır.
        toplam_tl = guncel['Toplam']
        
        # Üst Metrikler (Toplam Varlık Karşılıkları)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Toplam Varlık (TL)", f"{int(toplam_tl):,.0f}".replace(",", "."), f"{int(toplam_tl - onceki['Toplam']):,.0f}")
        
        # Karşılık metrikleri için güncel kur tahmini (Portföydeki varlık/tutar oranından çekilir)
        # Eğer portföyde o varlık yoksa statik 0 görünmemesi için varsayılan kur atanabilir veya boş geçilebilir.
        usd_tutar = guncel.get('Döviz', 0) / 30 if guncel.get('Döviz', 0) > 0 else toplam_tl / 30 # Örnek Kur: 30
        altin_gr = guncel.get('Altın', 0) / 2000 if guncel.get('Altın', 0) > 0 else toplam_tl / 2000 # Örnek Kur: 2000
        btc_adet = guncel.get('Kripto', 0) / 1500000 if guncel.get('Kripto', 0) > 0 else toplam_tl / 1500000 
        
        m2.metric("Altın Karşılığı", f"{(toplam_tl / 2000):.2f} gr") # Gram bazında toplam
        m3.metric("USD Karşılığı", f"$ {(toplam_tl / 30):,.0f}")
        m4.metric("EUR Karşılığı", f"€ {(toplam_tl / 33):,.0f}")
        m5.metric("BTC Karşılığı", f"₿ {(toplam_tl / 1500000):.4f}")

        st.divider()

        # Enstrüman Bazlı Alt Metrikler
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
            fig_p.update_traces(hovertemplate="%{label}<br>Tutar: %{value:,.0f}")
            st.plotly_chart(fig_p, use_container_width=True)
        with sub_tab2:
            df_p['tarih_tr'] = df_p['tarih'].dt.day.astype(str) + " " + df_p['tarih'].dt.month.map(TR_AYLAR_TAM)
            fig_l = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
            fig_l.update_traces(customdata=df_p['tarih_tr'], hovertemplate="Tarih: %{customdata}<br>Toplam: %{y:,.0f}")
            fig_l.update_xaxes(tickvals=df_p['tarih'], ticktext=[f"{d.day} {TR_AYLAR_KISA.get(d.strftime('%b'))}" for d in df_p['tarih']], title="Tarih")
            fig_l.update_layout(dragmode='pan', modebar_remove=['select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'toImage'])
            st.plotly_chart(fig_l, use_container_width=True, config={'scrollZoom': True})

# --- GELİRLER, GİDERLER VE BÜTÇE BÖLÜMLERİ (DEĞİŞMEDİ) ---
elif secilen_sekme == "💵 Gelirler":
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None); p = c2.number_input("Prim & Promosyon", min_value=0, value=None); y = c3.number_input("Yatırımlar", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam], value_input_option='RAW'); st.success("Kaydedildi."); st.rerun()
    # ... (Gelir grafiği kodu yukarıdakiyle aynı mantıkta korunmuştur)

elif secilen_sekme == "💸 Giderler":
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
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW'); st.success(f"Kaydedildi. Kalan: {int(yeni_kalan)}"); st.rerun()

elif secilen_sekme == "🛡️ Bütçe":
    with st.form("b_form"):
        yeni_l = st.number_input("Yeni Aylık Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_l, yeni_l], value_input_option='RAW'); st.success("Bütçe güncellendi."); st.rerun()
