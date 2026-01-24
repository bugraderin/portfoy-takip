import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")import streamlit as st
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
    
    # Mevcut Sayfalar
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    
    # Yeni Eklenen Fon Sayfaları
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris") # Portföy V2 kayıt sayfası
    ws_tefas_fiyat = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas_fiyat = spreadsheet.worksheet("BefasFonVerileri")

except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    input[type=number] { -moz-appearance: textfield; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
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

# --- SEKMELER (5 Sekme Yapıldı) ---
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
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0)) for e in enstrumanlar]
                tarihler = ws_portfoy.col_values(1)
                bugun = datetime.now().strftime('%Y-%m-%d')
                if bugun in tarihler:
                    ws_portfoy.update(f"A{tarihler.index(bugun)+1}:I{tarihler.index(bugun)+1}", [yeni_satir])
                else: ws_portfoy.append_row(yeni_satir)
                st.success("✅ Kaydedildi!"); st.rerun()

    # Grafik ve Analiz Kodları (Kısaltıldı ama işlevsel)
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
        m, p, y = c1.number_input("Maaş"), c2.number_input("Prim"), c3.number_input("Yatırım")
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y])
            st.success("Gelir eklendi!"); st.rerun()

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    gider_ikonlari = {"Genel": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kart": "💳", "Eğitim": "🎓", "Araba": "🚗", "Sağlık": "🏥"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(4)
        inputs = {isim: cols[i%4].number_input(f"{ikon} {isim}", min_value=0) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum(inputs.values())
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + list(inputs.values()))
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan_bakiye - toplam_h])
            st.success("Kaydedildi!"); st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Yönetimi")
    kb, ml = get_son_bakiye_ve_limit()
    ekle = st.number_input("Eklenecek Tutar", min_value=0)
    if st.button("Bakiyeye Ekle"):
        ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), ekle, kb + ekle])
        st.success("Bakiye güncellendi!"); st.rerun()

# --- SEKME 5: PORTFÖY V2 (YENİ SİSTEM) ---
with tab_v2:
    st.header("🚀 Gelişmiş Fon Takip Sistemi")
    
    try:
        # Fon Listesini Autocomplete için çek
        df_fonlar = pd.DataFrame(ws_fon_listesi.get_all_records())
        fon_secenekleri = [f"{row['Fon Kodu']} - {row['Fon Adı']}" for _, row in df_fonlar.iterrows()]
        
        secilen_full = st.selectbox("Fon Arayın (Kod veya Ad):", options=fon_secenekleri, index=None, placeholder="Örn: VGA")

        if secilen_full:
            secilen_kod = secilen_full.split(" - ")[0]
            secilen_ad = secilen_full.split(" - ")[1]
            
            c1, c2 = st.columns(2)
            with c1:
                kaynak = st.radio("Fiyat Kaynağı:", ["Tefas", "Befas"])
                ws_fiyat = ws_tefas_fiyat if kaynak == "Tefas" else ws_befas_fiyat
            with c2:
                lot = st.number_input("Lot Miktarı:", min_value=0.0, step=0.01, format="%.2f")

            # Fiyatı ilgili sayfadan çek
            fiyat_df = pd.DataFrame(ws_fiyat.get_all_records())
            fon_fiyat_row = fiyat_df[fiyat_df['Fon Kodu'] == secilen_kod]

            if not fon_fiyat_row.empty:
                son_fiyat = float(fon_fiyat_row.iloc[0]['Son Fiyat'])
                tutar = lot * son_fiyat
                st.metric(f"Anlık {kaynak} Fiyatı", f"{son_fiyat:.6f} TL")
                st.subheader(f"💰 Hesaplanan Tutar: {tutar:,.2f} TL")
                
                if st.button("📥 Portföyüme Ekle"):
                    # Veri_Giris: Tarih, Kod, Ad, Lot, Fiyat, Toplam, Kaynak
                    ws_veri_giris.append_row([datetime.now().strftime("%Y-%m-%d"), secilen_kod, secilen_ad, lot, son_fiyat, tutar, kaynak])
                    st.balloons(); st.success("Portföye eklendi!")
            else:
                st.warning("⚠️ Bu fonun fiyatı henüz bu kaynakta yok.")
                if st.button("➕ Fiyat Listesine Kod Olarak Ekle"):
                    ws_fiyat.append_row([secilen_kod, 0])
                    st.info("Kod eklendi, Apps Script fiyatı çekince burada görünecek.")

        st.divider()
        st.subheader("🗑️ Kayıtlı Fonları Yönet")
        v2_data = ws_veri_giris.get_all_records()
        if v2_data:
            df_v2 = pd.DataFrame(v2_data)
            st.dataframe(df_v2, use_container_width=True)
            
            silinecek = st.selectbox("Silinecek Kaydı Seçin (Kod):", df_v2['Kod'].unique())
            if st.button("Seçili Fonu Sil"):
                cell = ws_veri_giris.find(silinecek)
                ws_veri_giris.delete_rows(cell.row)
                st.success("Silindi!"); st.rerun()

    except Exception as e:
        st.error(f"V2 Hatası: {e}")
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

# --- ÖZEL CSS VE METRİK FONKSİYONU ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    
    /* Özel Mavi Metrik Stili */
    .neutral-metric { color: #007bff; font-weight: bold; font-size: 14px; margin-top: -10px; }
    
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

def custom_metric(label, value, delta_val, is_enstrument=False):
    """Değişim yoksa mavi tire gösteren özel metrik fonksiyonu"""
    if abs(delta_val) < 0.01:
        st.metric(label, value)
        st.markdown(f'<p class="neutral-metric">— 0.00%</p>', unsafe_allow_html=True)
    else:
        # Enstrümanlar için sadece yüzde, genel analiz için tutar + yüzde gösterir
        delta_text = f"{delta_val:.2f}%"
        st.metric(label, value, delta=delta_text)

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
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
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
                yuzde_deg = ((guncel_deger - baz_deger) / baz_deger) * 100
                display_val = f"{int(guncel_deger - baz_deger):,.0f} TL".replace(",", ".") if secilen_periyot == "1 Gün" else f"{int(guncel_deger):,.0f} TL".replace(",", ".")
                custom_metric(label_text, display_val, yuzde_deg)

        st.divider()
        # --- ENSTRÜMAN METRİKLERİ ---
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                g_val = float(guncel[e]); o_val = float(onceki[e])
                yuzde = ((g_val - o_val) / o_val * 100) if o_val > 0 else 0.0
                varlik_data.append({'Cins': e, 'Tutar': g_val, 'Delta': yuzde, 'Icon': enstruman_bilgi[e]})
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols_m = st.columns(4)
        for i, (idx, row) in enumerate(df_v.iterrows()):
            with cols_m[i % 4]:
                custom_metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), row['Delta'], is_enstrument=True)

        st.divider()
        sub_tab1, sub_tab2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        with sub_tab1:
            fig_p = px.pie(df_v, values='Tutar', names='Cins', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
        with sub_tab2:
            df_p_plot = df_p.groupby('tarih')['Toplam'].sum().reset_index()
            fig_p_line = px.line(df_p_plot, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
            st.plotly_chart(fig_p_line, use_container_width=True)

# --- GELİRLER/GİDERLER/BÜTÇE (AYNI KALDI) ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3); m = c1.number_input("Maaş", min_value=0); p = c2.number_input("Prim & Promosyon", min_value=0); y = c3.number_input("Yatırımlar", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam]); st.rerun()

with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    gider_ikonlari = {"Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kredi Kartı": "💳", "Kredi": "🏦", "Eğitim": "🎓", "Araba": "🚗", "Seyahat": "✈️", "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"}
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(3); inputs = {isim: cols[i % 3].number_input(f"{ikon} {isim}", min_value=0, value=None) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum([v or 0 for v in inputs.values()])
            if toplam_h > 0:
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [inputs[k] or 0 for k in gider_ikonlari.keys()], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan_bakiye - toplam_h], value_input_option='RAW'); st.rerun()

with tab_ayrilan:
    st.subheader("🛡️ Bütçe Ekleme"); kalan_bakiye, mevcut_limit = get_son_bakiye_ve_limit()
    with st.form("b_form"):
        yeni_eklenecek = st.number_input("Eklenecek Tutar (TL)", min_value=0)
        if st.form_submit_button("Bakiyeye Ekle"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_eklenecek, kalan_bakiye + yeni_eklenecek]); st.rerun()
