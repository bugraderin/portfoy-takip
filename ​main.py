# --- SEKME 2: GELİRLER (HATA GİDERİLDİ) ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None)
        p = c2.number_input("Prim", min_value=0, value=None)
        y = c3.number_input("Yatırım", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0], value_input_option='RAW')
            st.success("Gelir eklendi.")
            st.rerun()

    st.divider()
    st.subheader("🥧 Gelir Dağılımı")
    data_gelir = ws_gelir.get_all_records()
    if data_gelir:
        df_g_list = pd.DataFrame(data_gelir)
        
        # HATA ÖNLEYİCİ: Sütun isimlerindeki boşlukları temizle
        df_g_list.columns = df_g_list.columns.str.strip()
        
        # Sütunların varlığını kontrol et ve sayısal yap
        beklenen_sutunlar = ["Maaş", "Prim", "Yatırım"]
        mevcut_sutunlar = [col for col in beklenen_sutunlar if col in df_g_list.columns]
        
        for col in mevcut_sutunlar:
            df_g_list[col] = pd.to_numeric(df_g_list[col], errors='coerce').fillna(0)
        
        if len(df_g_list) > 0 and len(mevcut_sutunlar) > 0:
            son_gelir = df_g_list.iloc[-1]
            
            # Grafiği sadece mevcut olan sütunlarla oluştur
            g_pasta_data = pd.DataFrame({
                'Kategori': mevcut_sutunlar,
                'Tutar': [son_gelir[col] for col in mevcut_sutunlar]
            })
            g_pasta_data = g_pasta_data[g_pasta_data['Tutar'] > 0]
            
            if not g_pasta_data.empty:
                st.plotly_chart(px.pie(g_pasta_data, values='Tutar', names='Kategori', hole=0.4, title="Son Kaydedilen Gelir Dağılımı"), use_container_width=True)
            else:
                st.info("Henüz tutar içeren bir gelir verisi yok.")
        else:
            st.warning("Google Sheets sayfanızdaki başlıklar 'Maaş', 'Prim', 'Yatırım' şeklinde olmalıdır.")
