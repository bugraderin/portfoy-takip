import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import google.generativeai as genai

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
                'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- 1. GOOGLE SHEETS & AI BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    ws_ai_kaynak = spreadsheet.worksheet("AI") # Makalelerin olduğu sayfa
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- GEMINI AI YAPILANDIRMASI ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"], transport='rest')
else:
    st.warning("⚠️ GEMINI_API_KEY bulunamadı.")

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
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_ai = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🤖 AI Analist"])

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
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f", help=f"Son Değer: {int(float(son_kayitlar.get(e,0))):,.0f} TL") for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0)) for e in enstrumanlar]
                bugun = datetime.now().strftime('%Y-%m-%d')
                tarihler = ws_portfoy.col_values(1)
                if bugun in tarihler:
                    satir_no = tarihler.index(bugun) + 1
                    ws_portfoy.update(f"A{satir_no}:I{satir_no}", [yeni_satir])
                else:
                    ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                st.rerun()

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
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
        secilen_periyot = st.selectbox("Analiz Periyodu Seçin", list(periyotlar.keys()))
        hedef_tarih = guncel['tarih'] - timedelta(days=periyotlar[secilen_periyot])
        
        if len(df_p) > 1:
            baz_deger = float(df_p.iloc[-2]['Toplam']) if secilen_periyot == "1 Gün" else float(df_p[(df_p['tarih'] > hedef_tarih) & (df_p['tarih'] <= guncel['tarih'])]['Toplam'].mean() or 0)
            if baz_deger > 0:
                fark = float(guncel['Toplam']) - baz_deger
                yuzde_deg = (fark / baz_deger) * 100
                st.metric(f"{secilen_periyot} Değişimi", f"{int(fark):,.0f} TL".replace(",", "."), delta=f"{yuzde_deg:.2f}%")

        st.divider()
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = [{'Cins': e, 'Tutar': float(guncel[e]), 'Delta': f"{((float(guncel[e])-float(onceki[e]))/float(onceki[e])*100 if float(onceki[e])>0 else 0):.2f}%", 'Icon': enstruman_bilgi[e]} for e in enstrumanlar if guncel[e] > 0]
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols = st.columns(4)
        for i, (idx, row) in enumerate(df_v.iterrows()):
            cols[i % 4].metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), delta=row['Delta'])

        st.divider()
        sub1, sub2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        with sub1:
            st.plotly_chart(px.pie(df_v, values='Tutar', names='Cins', hole=0.4), use_container_width=True)
        with sub2:
            st.plotly_chart(px.line(df_p, x='tarih', y='Toplam', markers=True), use_container_width=True)

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

# --- SEKME 5: AI ANALİST (YENİ) ---
with tab_ai:
    st.header("🤖 AI Stratejik Danışman")
    if st.button("📊 Verileri ve Makaleleri Analiz Et"):
        try:
            # AI Sayfasındaki notları çek
            notlar_list = ws_ai_kaynak.col_values(1)[1:]
            egitim_notlari = " ".join([str(n) for n in notlar_list if n])
            
            # Model Yapılandırması
            model = genai.GenerativeModel(
    model_name='gemini-pro', # Bunu 'gemini-pro' yapıyoruz
    system_instruction=f"Sen Düzey 3 uzmanısın. Notların: {egitim_notlari}"
)
            
            # Veri Özeti
            varlik_ozeti = ", ".join([f"{e}: {int(guncel.get(e,0))} TL" for e in enstrumanlar if guncel.get(e,0) > 0])
            prompt = f"Varlıklar: {varlik_ozeti}. Toplam: {int(guncel['Toplam'])} TL. Kalan Bütçe: {int(kalan_bakiye)} TL. Stratejik yorum yap."
            
            with st.spinner("Analiz ediliyor..."):
                response = model.generate_content(prompt)
                st.info(response.text)
        except Exception as e:
            st.error(f"Hata: {e}")
