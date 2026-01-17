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
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }
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
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe"])

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
        # Haftalık (7 Gün) periyodu buraya eklendi
        periyotlar = {"1 Gün": 1, "1 Hafta": 7, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
        secilen_periyot = st.selectbox("Analiz Periyodu Seçin", list(periyotlar.keys()))
        hedef_tarih = guncel['tarih'] - timedelta(days=periyotlar[secilen_periyot])
        
        if len(df_p) > 1:
            guncel_deger = float(guncel['Toplam'])
            if secilen_periyot == "1 Gün":
                baz_deger = float(df_p.iloc[-2]['Toplam'])
                label_text = "Düne Göre Değişim"
            else:
                mask = (df_p['tarih'] > hedef_tarih) & (df_p['tarih'] <= guncel['tarih'])
                baz_deger = float(df_p.loc[mask, 'Toplam'].mean()) if not df_p.loc[mask].empty else 0
                label_text = f"{secilen_periyot} Ortalamasına Göre"

            if baz_deger > 0:
                fark = guncel_deger - baz_deger
                yuzde_deg = (fark / baz_deger) * 100
                
                # --- %0 DURUMUNDA MAVİ/NÖTR VE OKSUZ GÖSTERİM ---
                if abs(yuzde_deg) < 0.01:
                    st.metric(label_text, f"{int(guncel_deger):,.0f} TL".replace(",", "."), delta="0.00%", delta_color="off")
                else:
                    st.metric(label_text, f"{int(fark):,.0f} TL".replace(",", "."), delta=f"{yuzde_deg:.2f}%")

        st.divider()
        # --- ENSTRÜMAN METRİKLERİ ---
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                g_val = float(guncel[e]); o_val = float(onceki[e])
                yuzde = ((g_val - o_val) / o_val * 100) if o_val > 0 else 0.0
                varlik_data.append({'Cins': e, 'Tutar': g_val, 'Delta_Val': yuzde, 'Icon': enstruman_bilgi[e]})
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols_m = st.columns(4)
        for i, (idx, row) in enumerate(df_v.iterrows()):
            # Enstrüman Bazlı %0 Kontrolü
            if abs(row['Delta_Val']) < 0.01:
                cols_m[i % 4].metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), delta="0.00%", delta_color="off")
            else:
                cols_m[i % 4].metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), delta=f"{row['Delta_Val']:.2f}%")

        st.divider()
        sub_tab1, sub_tab2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        with sub_tab1:
            fig_p = px.pie(df_v, values='Tutar', names='Cins', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
        with sub_tab2:
            df_p_plot = df_p.groupby('tarih')['Toplam'].sum().reset_index()
            fig_p_line = px.line(df_p_plot, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
            st.plotly_chart(fig_p_line, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0)
        p = c2.number_input("Prim & Promosyon", min_value=0)
        y = c3.number_input("Yatırımlar", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam])
            st.success("Gelir eklendi!"); st.rerun()

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
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [inputs[k] or 0 for k in gider_ikonlari.keys()], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                st.success(f"Kaydedildi! Kalan: {int(yeni_kalan)} TL"); st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Ekleme")
    kalan_bakiye, mevcut_limit = get_son_bakiye_ve_limit()
    with st.form("b_form"):
        yeni_eklenecek = st.number_input("Eklenecek Tutar (TL)", min_value=0)
        if st.form_submit_button("Bakiyeye Ekle"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_eklenecek, kalan_bakiye + yeni_eklenecek])
            st.success("Bakiye güncellendi!"); st.rerun()
