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
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    /* Metrik fontları */
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    
    /* Input oklarını ve Streamlit butonlarını gizler (Kutuyu kapatmaz) */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type=number] {
        -moz-appearance: textfield;
    }
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
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
            if temp_data:
                df_temp = pd.DataFrame(temp_data)
                son_kayitlar = df_temp.iloc[-1]
            else:
                son_kayitlar = {e: 0.0 for e in enstrumanlar}
        except:
            son_kayitlar = {e: 0.0 for e in enstrumanlar}

        with st.form("p_form", clear_on_submit=True):
            p_in = {}
            for e in enstrumanlar:
                try:
                    son_val = float(son_kayitlar.get(e, 0))
                except:
                    son_val = 0.0
                
                p_in[e] = st.number_input(
                    f"{enstruman_bilgi[e]} {e}", 
                    min_value=0.0, 
                    value=None, 
                    format="%.f",
                    help=f"Son Kayıtlı Değer: {int(son_val):,.0f} TL"
                )

            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')]
                for e in enstrumanlar:
                    val = p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0))
                    yeni_satir.append(val)
                
                bugun = datetime.now().strftime('%Y-%m-%d')
                tarihler = ws_portfoy.col_values(1)
                
                if bugun in tarihler:
                    satir_no = tarihler.index(bugun) + 1
                    ws_portfoy.update(f"A{satir_no}:I{satir_no}", [yeni_satir])
                    st.success(f"📅 {bugun} tarihli kaydınız güncellendi!")
                else:
                    ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                    st.success("✅ Yeni gün kaydı başarıyla oluşturuldu!")
                
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

        # --- TEK VE DOĞRU DEĞİŞİM ANALİZİ BLOĞU ---
        st.write("### ⏱️ Değişim Analizi")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
        secilen_periyot = st.selectbox("Analiz Periyodu Seçin", list(periyotlar.keys()))
        
        gun_farki = periyotlar[secilen_periyot]
        hedef_tarih = guncel['tarih'] - timedelta(days=gun_farki)
        
        if not df_p.empty and len(df_p) > 1:
            guncel_deger = float(guncel['Toplam'])
            
            if secilen_periyot == "1 Gün":
                baz_deger = float(df_p.iloc[-2]['Toplam'])
                label_text = "Düne Göre Değişim"
            else:
                mask = (df_p['tarih'] > hedef_tarih) & (df_p['tarih'] <= guncel['tarih'])
                periyot_verileri = df_p.loc[mask]
                baz_deger = float(periyot_verileri['Toplam'].mean()) if not periyot_verileri.empty else 0
                label_text = f"{secilen_periyot} Ortalamasına Göre"

            if baz_deger > 0:
                fark = guncel_deger - baz_deger
                yuzde_deg = (fark / baz_deger) * 100
                delta_metni_analiz = f"{yuzde_deg:.2f}%"
                
                # Ekrana basan tek komut bu olmalı
                st.metric(label_text, f"{int(fark):,.0f} TL".replace(",", "."), delta=delta_metni_analiz)
            
            if secilen_periyot != "1 Gün":
                st.caption(f"ℹ️ Bugün, son {secilen_periyot} içindeki genel varlık ortalamanızdan ne kadar saptığınızı görüyorsunuz.")
        
        st.divider()
        
        # --- HİBRİT ANALİZ BLOĞU ---
        if not df_p.empty and len(df_p) > 1:
            guncel_deger = guncel['Toplam']
            
            if secilen_periyot == "1 Gün":
                # Düne göre net fark
                onceki_deger = df_p.iloc[-2]['Toplam']
                fark = guncel_deger - onceki_deger
                yuzde_deg = (fark / onceki_deger) * 100 if onceki_deger > 0 else 0
                label_text = "Düne Göre Değişim"
            else:
                # Periyodun ortalamasına göre fark
                mask = (df_p['tarih'] > hedef_tarih) & (df_p['tarih'] <= guncel['tarih'])
                periyot_verileri = df_p.loc[mask]
                
                if not periyot_verileri.empty:
                    periyot_ortalamasi = periyot_verileri['Toplam'].mean()
                    fark = guncel_deger - periyot_ortalamasi
                    yuzde_deg = (fark / periyot_ortalamasi) * 100 if periyot_ortalamasi > 0 else 0
                    label_text = f"{secilen_periyot} Ortalamasına Göre"
                else:
                    fark, yuzde_deg, label_text = 0, 0, "Veri Yetersiz"

            st.metric(label_text, f"{int(fark):,.0f} TL".replace(",", "."), f"%{yuzde_deg:.2f}")
            if secilen_periyot != "1 Gün":
                st.caption(f"ℹ️ Bugün, son {secilen_periyot} içindeki genel varlık ortalamanızdan ne kadar saptığınızı görüyorsunuz.")
        else:
            st.info("Kıyaslama yapabilmek için en az 2 farklı günlük kayıt gereklidir.")

        st.divider()
        # --- ENSTRÜMAN METRİKLERİ BÖLÜMÜ (RENK HATASI DÜZELTİLDİ) ---
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = [] 
        
        for e in enstrumanlar:
            if guncel[e] > 0:
                guncel_val = float(guncel[e])
                onceki_val = float(onceki[e])
                degisim_tutari = guncel_val - onceki_val
                
                if onceki_val > 0:
                    yuzde = (degisim_tutari / onceki_val) * 100
                else:
                    yuzde = 100.0 if degisim_tutari > 0 else 0.0
                
                # KRİTİK DÜZELTME: 
                # % işaretini sona aldık. Eğer sayı negatifse metin "-0.20%" olur.
                # Streamlit en baştaki "-" işaretini görünce otomatik kırmızı yapar.
                delta_metni = f"{yuzde:.2f}%"
                
                varlik_data.append({
                    'Cins': e, 
                    'Tutar': guncel_val, 
                    'Delta': delta_metni,
                    'Icon': enstruman_bilgi[e]
                })
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols = st.columns(4)
        for i, (index, row) in enumerate(df_v.iterrows()):
            with cols[i % 4]:
                st.metric(
                    label=f"{row['Icon']} {row['Cins']}", 
                    value=f"{int(row['Tutar']):,.0f}".replace(",", "."), 
                    delta=row['Delta']
                )

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

    data_g = ws_gelir.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        df_g['tarih'] = pd.to_datetime(df_g['tarih'], errors='coerce')
        for col in ["Maaş", "Prim&Promosyon", "Yatırımlar", "Toplam"]:
            if col in df_g.columns: df_g[col] = pd.to_numeric(df_g[col], errors='coerce').fillna(0)
        df_g['tarih_tr'] = df_g['tarih'].dt.month.map(TR_AYLAR_TAM) + " " + df_g['tarih'].dt.year.astype(str)
        fig_gl = px.line(df_g, x='tarih', y='Toplam', markers=True, title="Aylık Gelir Gelişimi")
        fig_gl.update_traces(customdata=df_g['tarih_tr'], hovertemplate="Dönem: %{customdata}<br>Gelir: %{y:,.0f}")
        fig_gl.update_xaxes(tickvals=df_g['tarih'], ticktext=[f"{TR_AYLAR_KISA.get(d.strftime('%b'))} {d.year}" for d in df_g['tarih']], title="Dönem")
        fig_gl.update_layout(dragmode='pan', modebar_remove=['select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'toImage'])
        st.plotly_chart(fig_gl, use_container_width=True, config={'scrollZoom': True})

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

    data_gi = ws_gider.get_all_records()
    if data_gi:
        df_gi = pd.DataFrame(data_gi)
        kats = list(gider_ikonlari.keys())
        for c in kats:
            if c in df_gi.columns: df_gi[c] = pd.to_numeric(df_gi[c], errors='coerce').fillna(0)
        top_gi = df_gi[kats].sum().reset_index()
        top_gi.columns = ['Kategori', 'Tutar']
        top_gi['Etiket'] = top_gi['Kategori'].map(lambda x: f"{gider_ikonlari.get(x, '')} {x}")
        if top_gi['Tutar'].sum() > 0:
            st.divider()
            fig_g_pie = px.pie(top_gi[top_gi['Tutar']>0], values='Tutar', names='Etiket', hole=0.4, title="Toplam Gider Dağılımı", color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_g_pie.update_traces(hovertemplate="%{label}<br>Tutar: %{value:,.0f}")
            st.plotly_chart(fig_g_pie, use_container_width=True)

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    with st.form("b_form"):
        yeni_l = st.number_input("Yeni Aylık Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_l, yeni_l], value_input_option='RAW')
            st.success("Bütçe güncellendi."); st.rerun()
