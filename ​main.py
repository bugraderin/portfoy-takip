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
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    
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
                try: son_val = float(son_kayitlar.get(e, 0))
                except: son_val = 0.0
                p_in[e] = st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f", help=f"Son Değer: {int(son_val):,.0f} TL")

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
                    st.success("📅 Güncellendi!")
                else:
                    ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                    st.success("✅ Kaydedildi!")
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

        # --- ⏱️ DEĞİŞİM ANALİZİ  ---
        st.write("### ⏱️ Değişim Analizi")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
        secilen_periyot = st.selectbox("Analiz Periyodu Seçin", list(periyotlar.keys()))
        
        hedef_tarih = guncel['tarih'] - timedelta(days=periyotlar[secilen_periyot])
        
        if not df_p.empty and len(df_p) > 1:
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
                st.metric(label_text, f"{int(fark):,.0f} TL".replace(",", "."), delta=f"{yuzde_deg:.2f}%")
            
            if secilen_periyot != "1 Gün":
                st.caption(f"ℹ️ Bugün, son {secilen_periyot} içindeki genel varlık ortalamanızdan ne kadar saptığınızı görüyorsunuz.")

        st.divider()
        # --- ENSTRÜMAN METRİKLERİ  ---
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                guncel_val = float(guncel[e]); onceki_val = float(onceki[e])
                degisim = guncel_val - onceki_val
                yuzde = (degisim / onceki_val * 100) if onceki_val > 0 else 0.0
                varlik_data.append({'Cins': e, 'Tutar': guncel_val, 'Delta': f"{yuzde:.2f}%", 'Icon': enstruman_bilgi[e]})
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols_m = st.columns(4)
        for i, (idx, row) in enumerate(df_v.iterrows()):
            cols_m[i % 4].metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), delta=row['Delta'])

        st.divider()
        sub_tab1, sub_tab2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        
        with sub_tab1:
            df_v['Etiket'] = df_v['Icon'] + " " + df_v['Cins']
            fig_p = px.pie(df_v, values='Tutar', names='Etiket', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
            
        with sub_tab2:
            # Dikey çizgiyi engellemek için aynı tarihlerdeki verileri topla
            df_p_plot = df_p.groupby('tarih')['Toplam'].sum().reset_index()
            
            fig_p_line = px.line(df_p_plot, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri")
            fig_p_line.update_traces(
                line=dict(color='#007bff', width=3),
                marker=dict(size=8, symbol='circle', color='#007bff', line=dict(width=1, color='white'))
            )
            fig_p_line.update_layout(
                dragmode='pan',
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(gridcolor='#f0f0f0', title=""),
                xaxis=dict(showgrid=False, title="")
            )
            fig_p_line.update_xaxes(
                tickvals=df_p_plot['tarih'], 
                ticktext=[f"{d.day} {TR_AYLAR_KISA.get(d.strftime('%b'))}" for d in df_p_plot['tarih']]
            )
            st.plotly_chart(fig_p_line, use_container_width=True, config={
                'scrollZoom': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
            })

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
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, toplam])
            st.success("Gelir eklendi!")
            st.rerun()

    data_g = ws_gelir.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        df_g.columns = [c.lower() for c in df_g.columns]
        
        if 'tarih' in df_g.columns:
            # Tarih formatını garantiye al ve temizle
            df_g['tarih'] = pd.to_datetime(df_g['tarih'], errors='coerce')
            df_g = df_g.dropna(subset=['tarih']).sort_values('tarih')

            # --- SÜTUNLARI BURADA TANIMLIYORUZ (Hata Çözümü) ---
            col1, col2 = st.columns(2)

            with col1:
                gelir_cols = [c for c in df_g.columns if c not in ['tarih', 'toplam']]
                gelir_toplam = df_g[gelir_cols].sum()
                fig_g_pie = px.pie(values=gelir_toplam.values, names=gelir_toplam.index, 
                                 title="Gelir Kaynakları", hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_g_pie, use_container_width=True)
            
            with col2:
                # Dikey çizgiyi engellemek için aynı tarihleri topla
                df_g_plot = df_g.groupby('tarih')['toplam'].sum().reset_index()

                # İsteğine uygun modern çizgi grafik
                fig_g_area = px.line(df_g_plot, x='tarih', y='toplam', markers=True, title="Gelir Akışı Seyri")
                
                # Çizgi ve Nokta Ayarları (image_6af9d8 stilinde)
                fig_g_area.update_traces(
                    line=dict(color='#007bff', width=3),
                    marker=dict(size=10, symbol='circle', color='#007bff', line=dict(width=2, color='white'))
                )
                
                fig_g_area.update_layout(
                    dragmode='pan',
                    hovermode='x unified',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(gridcolor='#f0f0f0', title=""),
                    xaxis=dict(showgrid=False, title="")
                )

                # Türkçe Tarih Formatı
                fig_g_area.update_xaxes(
                    tickvals=df_g_plot['tarih'], 
                    ticktext=[f"{d.day} {TR_AYLAR_KISA.get(d.strftime('%b'))}" for d in df_g_plot['tarih']]
                )
                
                # Gereksiz butonları temizle (image_6ae390 çözümü)
                st.plotly_chart(fig_g_area, use_container_width=True, config={
                    'scrollZoom': True,
                    'displaylogo': False,
                    'modeBarButtonsToRemove': [
                        'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 
                        'zoomOut2d', 'autoScale2d', 'resetScale2d'
                    ]
                })
# --- SEKME 3: GİDERLER (BİRLEŞTİRİLMİŞ) ---
with tab_gider:
    # 1. Mevcut Bakiye Bilgisini Göster
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    
    # 2. Harcama Giriş Formu
    gider_ikonlari = {
        "Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", 
        "Aidat": "🏢", "Kredi Kartı": "💳", "Kredi": "🏦", 
        "Eğitim": "🎓", "Araba": "🚗", "Seyahat": "✈️", 
        "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"
    }
    
    with st.form("gi_form", clear_on_submit=True):
        st.write("### 📝 Yeni Harcama Gir")
        cols = st.columns(3)
        # Form inputlarını oluştur
        inputs = {isim: cols[i % 3].number_input(f"{ikon} {isim}", min_value=0, value=None) 
                 for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        
        submit_gider = st.form_submit_button("✅ Harcamayı Kaydet")
        
        if submit_gider:
            toplam_h = sum([v or 0 for v in inputs.values()])
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                
                # Giderler sayfasına satır ekle
                yeni_gider_satiri = [datetime.now().strftime('%Y-%m-%d')] + [inputs[k] or 0 for k in gider_ikonlari.keys()]
                ws_gider.append_row(yeni_gider_satiri, value_input_option='RAW')
                
                # Bütçe/Ayrılan Tutar sayfasını güncelle
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                
                st.success(f"Harcama kaydedildi! Yeni Kalan: {int(yeni_kalan)} TL")
                st.rerun()
            else:
                st.warning("Lütfen en az bir harcama kalemi giriniz.")

    st.divider()

    # 3. Harcama Analiz Grafiği (Pasta Grafiği)
    st.write("### 📊 Harcama Dağılımı")
    try:
        data_gi = ws_gider.get_all_records()
        if data_gi:
            df_gi = pd.DataFrame(data_gi)
            # Sütun isimlerini küçük harfe çevirerek standardize et
            df_gi.columns = [c.lower() for c in df_gi.columns]
            
            # 'tarih' sütunu haricindeki tüm sütunları topla (kategoriler)
            harcama_ozet = df_gi.drop(columns=['tarih'], errors='ignore').sum()
            # Sadece harcama yapılmış (0'dan büyük) kategorileri filtrele
            harcama_ozet = harcama_ozet[harcama_ozet > 0]
            
            if not harcama_ozet.empty:
                fig_gi_pie = px.pie(
                    values=harcama_ozet.values, 
                    names=harcama_ozet.index.str.title(), # Baş harfleri büyük yap
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_gi_pie.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_gi_pie, use_container_width=True)
            else:
                st.info("Henüz grafik oluşturulacak kadar harcama verisi yok.")
        else:
            st.info("Henüz kaydedilmiş harcama bulunmuyor.")
    except Exception as e:
        st.error(f"Grafik yüklenirken hata oluştu: {e}")

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Ekleme")
    kalan_bakiye, mevcut_limit = get_son_bakiye_ve_limit()
    st.write(f"Şu anki Kalan Bakiye: **{int(kalan_bakiye):,.0f} TL**")
    with st.form("b_form"):
        yeni_eklenecek = st.number_input("Eklenecek Tutar (TL)", min_value=0)
        if st.form_submit_button("Bakiyeye Ekle"):
            yeni_toplam_kalan = kalan_bakiye + yeni_eklenecek
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_eklenecek, yeni_toplam_kalan])
            st.success("Bakiye güncellendi!"); st.rerun()
