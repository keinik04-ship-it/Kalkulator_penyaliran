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
    volume = (h / 3) * (luas_alas + luas_atas + math.sqrt(luas_alas * luas_alas))
    return volume, s_atas

def run_streamlit_app():
    st.set_page_config(page_title="Kalkulator Desain Pengendapan Pro", layout="wide")
    st.title("🌊 Sistem Desain Kolam Pengendapan & Analisis Hidrograf")
    st.markdown("---")

    # --- SIDEBAR: INPUT PARAMETER ---
    st.sidebar.header("📥 Parameter Input")
    
    with st.sidebar.expander("1. Hidrologi (Kirpich & SCS)", expanded=True):
        area_ha = st.number_input("Luas Catchment (Hektar)", value=116.0, step=0.1)
        c_limpasan = st.number_input("Koefisien Limpasan (C)", value=0.90, min_value=0.0, max_value=1.0, step=0.01)
        slope = st.number_input("Average Watershed Slope (S)", value=0.250, format="%.3f")
        length_m = st.number_input("Length of Divide (L) meter", value=1300.0)
        tr_effective = st.number_input("Duration of Effective Rainfall (tr) jam", value=2.0, step=0.1)
        intensitas = 25.04  
        durasi_simulasi = st.slider("Durasi Simulasi Grafik (Jam)", 1, 48, 24)
        
        # --- PERHITUNGAN KIRPICH ---
        tc_menit = (0.01947 * (length_m**0.77)) / (slope**0.385)
        tc_jam = tc_menit / 60 
        tp_lag = 0.6 * tc_jam
        Tp_peak = (tr_effective / 2) + tp_lag
        
        area_km2 = area_ha / 100
        # --- RUMUS PEAK DISCHARGE (QP) ---
        Qp = 2.08 * area_km2 / Tp_peak
        # --- RUMUS DEBIT PUNCAK ---
        debit_puncak = 0.00278 * c_limpasan * intensitas * area_ha

    with st.sidebar.expander("2. Operasional & Fisika", expanded=False):
        massa_jenis_g = st.number_input("Massa Jenis Padatan (g/m³)", value=2500000.0)
        d_mm = st.number_input("Diameter Partikel (mm)", value=0.05, format="%.4f")
        pa = st.number_input("Massa Jenis Air (kg/m³)", value=1000.0)
        miu = st.number_input("Viskositas (Pa·s)", value=0.001, format="%.4f")

    with st.sidebar.expander("3. Konstruksi Kolam", expanded=False):
        kedalaman = st.number_input("Kedalaman Kolam (m)", value=2.0, step=0.1)
        jumlah_kolam = st.number_input("Total Jumlah Kolam", min_value=1, value=3, step=1)
        kemiringan = 60 

    # --- DATA RATIO MANUAL (33 NILAI) ---
    time_ratios = [
        0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 
        1.6, 1.7, 1.8, 1.9, 2, 2.2, 2.4, 2.6, 2.8, 3, 3.2, 3.4, 3.6, 3.8, 4, 4.5, 5
    ]
    discharge_ratios = [
        0, 0.03, 0.1, 0.19, 0.31, 0.47, 0.66, 0.82, 0.93, 0.99, 1, 0.99, 0.93, 0.86, 
        0.78, 0.68, 0.56, 0.46, 0.39, 0.33, 0.28, 0.207, 0.147, 0.107, 0.077, 0.055, 
        0.04, 0.029, 0.021, 0.015, 0.011, 0.005, 0
    ]

    # --- LOGIKA PERHITUNGAN TABEL ---
    data_list = []
    for i in range(len(time_ratios)):
        tr = time_ratios[i]
        dr = discharge_ratios[i]
        
        t_jam = (tr * Tp_peak) + tc_jam
        t_sec = t_jam * 3600
        debit_q = Qp * dr
        debit_t10 = debit_q * 25.04 / 10
        
        data_list.append({
            "Time Ratio": tr,
            "Discharge Ratio": dr,
            "Time (t) jam": t_jam,
            "Time (s)": t_sec,
            "Debit (q)": debit_q,
            "Debit (T=10)": debit_t10
        })

    df_full = pd.DataFrame(data_list)
    
    # --- PERHITUNGAN VOLUME (n ke n+1) ---
    vols = []
    for i in range(len(df_full)):
        if i < len(df_full) - 1:
            vol_step = (df_full.loc[i+1, "Time (s)"] - df_full.loc[i, "Time (s)"]) * \
                       (df_full.loc[i, "Debit (T=10)"] + df_full.loc[i+1, "Debit (T=10)"]) / 2
            vols.append(vol_step)
        else:
            vols.append(0.0)
    
    df_full["Volume"] = vols
    df_full["Akumulasi Volume"] = df_full["Volume"].cumsum()

    # --- DEBIT MAX DARI TABEL ---
    debit_max_t10 = df_full["Debit (T=10)"].max()

    df_plot = df_full[df_full["Time (t) jam"] <= durasi_simulasi]
    total_vol_limpasan = df_full["Akumulasi Volume"].iloc[-1]

    # --- PERHITUNGAN FISIK ---
    ps_kg = massa_jenis_g / 1000
    v_stokes = (9.8 * ((d_mm/1000)**2) * (ps_kg - pa)) / (18 * miu) if miu > 0 else 0
    luas_total_butuh = (Qp * 1.5) / v_stokes if v_stokes > 0 else 0
    luas_u1 = luas_total_butuh / 3
    vol_u1, sa1 = hitung_volume_miring(luas_u1, kedalaman, kemiringan)
    kapasitas_sistem = vol_u1 * jumlah_kolam

    # --- DASHBOARD ---
    st.subheader("Perhitungan Hidrologi")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Qp", f"{Qp:.3f} m³/s")
    col2.metric("Debit Puncak", f"{debit_puncak:.3f} m³/s")
    col3.metric("Debit Max (T=10)", f"{debit_max_t10:.3f} m³/s")
    col4.metric("V. Stokes", f"{v_stokes:.6f} m/s")
    col5.metric("Total Vol. Masuk", f"{total_vol_limpasan:.0f} m³")
    col6.metric("Kapasitas Sistem", f"{kapasitas_sistem:.0f} m³")

    # --- TOMBOL LINK SPREADSHEET ---
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1fdBN-JkzGABXV7f0EB6UMblUjvyZEUi58l1lVkEuqhk/edit?gid=207338239&pli=1&authuser=0#gid=207338239"
    st.link_button("📂 Perhitungan TSS", spreadsheet_url, use_container_width=True, type="primary")


    col7, col8, col9, col10 = st.columns(4)
    col7.metric("Peak Time (TP)", f"{Tp_peak:.3f} Jam")
    col8.metric("Time of Conc. (TC)", f"{tc_menit:.2f} Min")
    col9.metric("Lag Time (tp)", f"{tp_lag:.3f} Jam")
    col10.metric("Luas Catchment", f"{area_ha} Ha")

    st.markdown("---")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📈 Hidrograf Aliran (SCS-Kirpich)")
        st.area_chart(df_plot.set_index("Time (t) jam")["Debit (T=10)"])
    with col_right:
        st.subheader("📉 Akumulasi Volume Limpasan")
        st.line_chart(df_plot.set_index("Time (t) jam")["Akumulasi Volume"])

    st.markdown("---")
    st.subheader("📋 Tabel Perhitungan Hidrograf")
    if st.button("Lihat Tabel Analisis Lengkap"):
        st.dataframe(df_full, use_container_width=True)

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

    st.caption("Volume: integrasi maju (n ke n+1). Qp: 2.08 * A / Tp. Debit Puncak: 0.00278 * C * I * A.")

if __name__ == "__main__":
    if st.runtime.exists():
        run_streamlit_app()
    else:
        sys.argv = ["streamlit", "run", resolve_path(__file__), "--server.headless=false"]
        sys.exit(stcli.main())
