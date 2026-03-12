import streamlit as st
import streamlit.web.cli as stcli
import math
import os
import sys
import pandas as pd

# --- FUNGSI WRAPPER UNTUK EXECUTABLE ---
def resolve_path(path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.abspath(os.path.join(os.getcwd(), path))

def hitung_volume_miring(luas_alas, h, sudut_derajat=60):
    s_bawah = math.sqrt(luas_alas)
    sudut_rad = math.radians(sudut_derajat)
    x = h / math.tan(sudut_rad)
    s_atas = s_bawah + (2 * x)
    luas_atas = s_atas ** 2
    # Rumus Frustum (Limas Terpancung)
    volume = (h / 3) * (luas_alas + luas_atas + math.sqrt(luas_alas * luas_atas))
    return volume, s_atas

def run_streamlit_app():
    st.set_page_config(page_title="Kalkulator Desain Pengendapan Pro", layout="wide")
    st.title("🌊 Sistem Desain Kolam Pengendapan & Analisis Hidrograf")
    st.markdown("---")

    # --- SIDEBAR: INPUT PARAMETER ---
    st.sidebar.header("📥 Parameter Input")
    
    st.sidebar.markdown("### 🔗 External Link")
    st.sidebar.link_button("📊 Perhitungan TSS", "https://docs.google.com/spreadsheets/d/1fdBN-JkzGABXV7f0EB6UMblUjvyZEUi58l1lVkEuqhk/edit?gid=207338239#gid=207338239")
    st.sidebar.markdown("---")
    
    with st.sidebar.expander("1. Hidrologi (Sesuai Gambar)", expanded=True):
        area_ha = st.number_input("Luas Catchment (Hektar)", value=55.0, step=0.1)
        c_limpasan = st.number_input("Koefisien Limpasan (C)", value=0.50, min_value=0.0, max_value=1.0, step=0.01)
        intensitas = 25.04  
        durasi_simulasi = st.slider("Durasi Simulasi (Jam)", 1, 10, 6)
        debit_puncak = 0.00278 * c_limpasan * intensitas * area_ha

    with st.sidebar.expander("2. Operasional & Fisika", expanded=True):
        tss_max = st.number_input("TSS Maksimal (mg/L)", value=100.0, step=1.0)
        massa_jenis_g = st.number_input("Massa Jenis Padatan (g/m³)", value=2500000.0)
        d_mm = st.number_input("Diameter Partikel (mm)", value=0.05, format="%.4f")
        pa = st.number_input("Massa Jenis Air (kg/m³)", value=1000.0)
        miu = st.number_input("Viskositas (Pa·s)", value=0.001, format="%.4f")

    with st.sidebar.expander("3. Konstruksi Kolam", expanded=True):
        kedalaman = st.number_input("Kedalaman Kolam (m)", value=2.0, step=0.1)
        jumlah_kolam = st.number_input("Total Jumlah Kolam", min_value=1, value=3, step=1)
        kemiringan = 60 

    # --- LOGIKA HIDROGRAF & VOLUME AKUMULASI ---
    t_list = [x * 0.1 for x in range(durasi_simulasi * 10 + 1)] 
    tp = 1.054 
    
    q_list = []
    for t in t_list:
        if t == 0: q = 0
        else: q = debit_puncak * (t/tp) * math.exp(1 - (t/tp))
        q_list.append(q)

    df_hydro = pd.DataFrame({"Jam": t_list, "Debit (m³/s)": q_list})
    df_hydro['Vol_Step'] = df_hydro['Debit (m³/s)'].rolling(window=2).mean() * (0.1 * 3600)
    df_hydro['Akumulasi_Volume'] = df_hydro['Vol_Step'].fillna(0).cumsum()
    total_vol_limpasan = df_hydro['Akumulasi_Volume'].iloc[-1]

    # --- PERHITUNGAN TEKNIS (STOKES & WAKTU ALIR) ---
    ps_kg = massa_jenis_g / 1000
    g_gravity = 9.8
    d_m = d_mm / 1000
    
    # Kecepatan Pengendapan (Stokes)
    v_stokes = (g_gravity * (d_m**2) * (ps_kg - pa)) / (18 * miu) if miu > 0 else 0
    
    # Luas total butuh berdasarkan Q Puncak x Safety Factor 1.5
    luas_total_butuh = (debit_puncak * 1.5) / v_stokes if v_stokes > 0 else 0

    # Perhitungan Unit 1
    luas_u1 = luas_total_butuh / 3
    vol_u1, sa1 = hitung_volume_miring(luas_u1, kedalaman, kemiringan)
    v_air_1 = (debit_puncak * 1.25) / luas_u1 if luas_u1 > 0 else 0
    waktu_alir_1 = math.sqrt(luas_u1) / v_air_1 if v_air_1 > 0 else 0

    # Perhitungan Unit Secondary
    if jumlah_kolam > 1:
        n_sec = jumlah_kolam - 1
        luas_sec = ((2/3) * luas_total_butuh) / n_sec
        vol_sec, sa_sec = hitung_volume_miring(luas_sec, kedalaman, kemiringan)
        v_air_sec = (debit_puncak * 1.25) / luas_sec if luas_sec > 0 else 0
        waktu_alir_sec = math.sqrt(luas_sec) / v_air_sec if v_air_sec > 0 else 0
        kapasitas_sistem = vol_u1 + (vol_sec * n_sec)
    else:
        kapasitas_sistem = vol_u1
        vol_sec, sa_sec, luas_sec, waktu_alir_sec = 0, 0, 0, 0

    # --- TAMPILAN DASHBOARD ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Debit Puncak (Qp)", f"{debit_puncak:.3f} m³/s")
    c2.metric("V. Stokes", f"{v_stokes:.6f} m/s")
    c3.metric("Total Vol. Masuk", f"{total_vol_limpasan:.0f} m³")
    c4.metric("Kapasitas Sistem", f"{kapasitas_sistem:.0f} m³")

    st.markdown("---")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📈 Hidrograf Aliran")
        st.area_chart(df_hydro.set_index("Jam")["Debit (m³/s)"])
    with col_right:
        st.subheader("📉 Akumulasi Volume Limpasan")
        st.line_chart(df_hydro.set_index("Jam")["Akumulasi_Volume"])

    st.markdown("---")
    tab1, tab2 = st.tabs(["Unit 1 (Primary)", "Unit Secondary"])
    
    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**Sisi Bawah:** {math.sqrt(luas_u1):.2f} m")
            st.write(f"**Sisi Atas:** {sa1:.2f} m")
            st.write(f"**Luas Alas:** {luas_u1:.2f} m²")
        with col_b:
            st.success(f"**Volume Kolam:** {vol_u1:.2f} m³")
            st.info(f"**Waktu Keluar:** {waktu_alir_1:.2f} detik")

    with tab2:
        if jumlah_kolam > 1:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Sisi Bawah:** {math.sqrt(luas_sec):.2f} m")
                st.write(f"**Sisi Atas:** {sa_sec:.2f} m")
                st.write(f"**Luas Alas:** {luas_sec:.2f} m²")
            with col_b:
                st.success(f"**Volume per Unit:** {vol_sec:.2f} m³")
                st.info(f"**Waktu Keluar:** {waktu_alir_sec:.2f} detik")
        else:
            st.info("Hanya menggunakan satu unit kolam utama.")

    st.caption("Aplikasi mengintegrasikan Hukum Stokes untuk kecepatan pengendapan dan Hidrograf Satuan untuk akumulasi volume.")

# --- ENTRY POINT ---
if __name__ == "__main__":
    if st.runtime.exists():
        run_streamlit_app()
    else:
        sys.argv = ["streamlit", "run", resolve_path(__file__), "--server.headless=false"]
        sys.exit(stcli.main())