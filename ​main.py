import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Portföy Yönetim Paneli")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# --- 2. VARLIK TANIMLARI ---
enstruman_bilgi = {
    'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
    'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
}
enstrumanlar = list(enstruman_bilgi.keys())

# --- 3. UI: VERİ GİRİŞ ALANI (SADECE TL) ---
with st.sidebar:
    st.header("📥 Veri Girişi")
    with st.form("veri_formu", clear_on_submit=True):
        inputs = {}
        for e in enstrumanlar:
            # İstediğin gibi sadece TL bazlı giriş
            inputs[e] = st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, step=100.0, format="%.0f")
        
        submit = st.form_submit_button("🚀 Kaydet", use_container_width=True)

if submit:
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [inputs[e] for e in enstrumanlar]
    worksheet.append_row(yeni_satir)
    st.toast("Veriler kaydedildi!", icon='✅')
    st.rerun()

# --- 4. VERİ İŞLEME ---
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    # Sayısal dönüşüm ve temizlik
    for col in df.columns:
        if col != 'tarih':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['Toplam'] = df[enstrumanlar].sum(axis=1)
    df['tarih'] = pd.to_datetime(df['tarih'])
    df = df.sort_values('tarih')
    
    guncel = df.iloc[-1]

    # ÖZET KARTLAR
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Varlık", f"{guncel['Toplam']:,.0f} TL")
    if len(df) > 1:
        degisim = guncel['Toplam'] - df['Toplam'].iloc[-2]
        yuzde = (degisim / df['Toplam'].iloc[-2]) * 100
        c2.metric("Günlük Değişim", f"{degisim:,.0f} TL", f"%{yuzde:.2f}")
    c3.metric("Kayıt Sayısı", len(df))

    st.divider()

    # --- 5. GRAFİKLER ---
    t1, t2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Grafiği"])
    
    with t1:
        # SIRALI VERİ HAZIRLIĞI
        raw_data = [{'Varlık': f"{enstruman_bilgi[e]} {e}", 'Değer': guncel[e]} for e in enstrumanlar if guncel[e] > 0]
        plot_df = pd.DataFrame(raw_data).sort_values(by='Değer', ascending=False)
        
        c_sol, c_sag = st.columns([1.2, 1])
        with c_sol:
            fig = px.pie(plot_df, values='Değer', names='Varlık', hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label', textposition='inside')
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=450)
            st.plotly_chart(fig, use_container_width=True)
            
        with c_sag:
            st.subheader("🔝 Varlık Payları")
            for _, row in plot_df.iterrows():
                p = (row['Değer'] / guncel['Toplam'])
                st.write(f"**{row['Varlık']}:** %{p*100:.1f}")
                st.progress(min(p, 1.0))

    with t2:
        st.line_chart(df.set_index('tarih')['Toplam'])

    # --- 6. PERFORMANS ANALİZİ (Geri Getirildi) ---
    st.divider()
    st.subheader("⏱️ Dönemsel Performans Analizi")
    periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
    secim = st.selectbox("Kıyaslama süresi seçin:", list(periyotlar.keys()))
    
    hedef_tarih = datetime.now() - timedelta(days=periyotlar[secim])
    gecmis_df = df[df['tarih'] <= hedef_tarih]
    baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df.iloc[0]
    
    st.info(f"Seçilen dönem başı ({baslangic['tarih'].date()}): **{baslangic['Toplam']:,.0f} TL**")
    
    # Sıralı Performans Kartları
    perf_cols = st.columns(4)
    # Mevcut varlıkları büyükten küçüğe kart olarak basıyoruz
    for i, (_, row) in enumerate(plot_df.iterrows()):
        varlik_adi = row['Varlık'].split(' ')[1] # Emoji ayıklama
        v_eski = baslangic.get(varlik_adi, 0)
        v_yeni = row['Değer']
        
        if v_eski > 0:
            fark_yuzde = ((v_yeni - v_eski) / v_eski) * 100
            perf_cols[i % 4].metric(row['Varlık'], f"{v_yeni:,.0f} TL", f"%{fark_yuzde:.1f}")
        else:
            perf_cols[i % 4].metric(row['Varlık'], f"{v_yeni:,.0f} TL", "Yeni")

    # --- 7. GEÇMİŞ KAYITLAR (Geri Getirildi) ---
    st.divider()
    with st.expander("📄 Tüm Geçmiş Kayıtları Listele"):
        st.dataframe(df.sort_values('tarih', ascending=False), use_container_width=True)

else:
    st.info("💡 Başlamak için sol menüden veri girişi yapın.")
