import pandas as pd
import plotly.express as px
import streamlit as st

from src.saw import jalankan_saw, BOBOT_ROC, KRITERIA, NAMA_KRITERIA
from src.data import baca_dan_validasi, TEMPLATE_CSV

st.set_page_config(page_title="SPK Intervensi Kesehatan Palembang", layout="wide")
WARNA_PRIORITAS = {"Tinggi": "#B3261E", "Sedang": "#E3A21A", "Rendah": "#5B8C9A"}

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.5rem; max-width: 1200px;}
    div[data-testid="stMetricValue"] {font-size: 1.6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Sidebar: data ---
st.sidebar.header("Data")
berkas = st.sidebar.file_uploader("Upload dataset (CSV)", type="csv")
st.sidebar.download_button(
    "Unduh template CSV", TEMPLATE_CSV, "template_data_kecamatan.csv", "text/csv"
)

sumber = berkas if berkas is not None else "data/data_kecamatan.csv"
df, errors = baca_dan_validasi(sumber)
if errors:
    st.error("Dataset tidak valid:")
    for e in errors:
        st.markdown(f"- {e}")
    st.stop()

st.sidebar.caption(
    f"Sumber: {berkas.name if berkas is not None else 'data bawaan'} ({len(df)} kecamatan)"
)
st.sidebar.divider()

# --- Sidebar: bobot kriteria ---
def reset_bobot():
    for k in KRITERIA:
        st.session_state[f"w_{k}"] = round(BOBOT_ROC[k] * 100, 2)


for k in KRITERIA:
    st.session_state.setdefault(f"w_{k}", round(BOBOT_ROC[k] * 100, 2))

st.sidebar.header("Bobot kriteria")
simulasi = st.sidebar.toggle("Mode simulasi bobot (what-if)", value=False)

if not simulasi:
    st.sidebar.caption("Bobot resmi: ROC berjenjang (terkunci)")
    for k in KRITERIA:
        st.sidebar.write(f"**{k}** - {NAMA_KRITERIA[k]}: {BOBOT_ROC[k] * 100:.2f}%")
    bobot = BOBOT_ROC
else:
    for k in KRITERIA:
        st.sidebar.slider(
            f"{k} - {NAMA_KRITERIA[k]}", 0.0, 100.0, step=0.01, key=f"w_{k}"
        )
    total = sum(st.session_state[f"w_{k}"] for k in KRITERIA)
    if abs(total - 100) < 0.01:
        st.sidebar.success(f"Total bobot: {total:.2f}%")
    else:
        st.sidebar.warning(
            f"Total bobot: {total:.2f}% (bukan 100%). "
            "Bobot dinormalisasi otomatis agar totalnya 100%."
        )
    st.sidebar.button("Reset ke bobot ROC", on_click=reset_bobot)

    if total == 0:
        st.error("Total bobot 0%. Naikkan minimal satu slider.")
        st.stop()
    bobot = {k: st.session_state[f"w_{k}"] / total for k in KRITERIA}

hasil = jalankan_saw(df, bobot)

# --- Siapkan tabel ranking + tingkat prioritas ---
ranking = hasil["ranking"].reset_index()  # kolom: Kecamatan, Skor, Peringkat
n = len(ranking)
ranking["Prioritas"] = pd.cut(
    ranking["Peringkat"],
    bins=[0, n / 3, 2 * n / 3, n],
    labels=["Tinggi", "Sedang", "Rendah"],
).astype(str)

# --- Judul ---
st.title("Prioritas Intervensi Kesehatan Kota Palembang")
st.caption("Sistem pendukung keputusan dengan metode SAW dan bobot ROC berjenjang")
if simulasi:
    st.warning(
        "Mode simulasi aktif: hasil di bawah memakai bobot hasil geseran, "
        "bukan bobot ROC resmi."
    )

tab_ringkasan, tab_tahapan, tab_sens = st.tabs(
    ["Ringkasan", "Tahapan perhitungan", "Sensitivitas bobot"]
)

# =====================================================================
# TAB 1: RINGKASAN
# =====================================================================
with tab_ringkasan:
    # Kartu ringkasan
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kecamatan dianalisis", n, border=True)
    c2.metric("Prioritas utama", ranking.iloc[0]["Kecamatan"], border=True)
    c3.metric("Skor tertinggi", f"{ranking['Skor'].max():.4f}", border=True)
    c4.metric("Skor terendah", f"{ranking['Skor'].min():.4f}", border=True)

    # Bar chart ranking
    st.subheader("Ranking skor SAW (Vi)")
    fig = px.bar(
        ranking,
        x="Skor",
        y="Kecamatan",
        orientation="h",
        color="Prioritas",
        color_discrete_map=WARNA_PRIORITAS,
        category_orders={
            "Kecamatan": ranking["Kecamatan"].tolist(),
            "Prioritas": ["Tinggi", "Sedang", "Rendah"],
        },
        text="Skor",
        hover_data={"Skor": ":.4f", "Peringkat": True},
    )
    fig.update_traces(texttemplate="%{x:.3f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(title=None)
    fig.update_layout(
        height=max(400, 32 * n + 100),
        legend=dict(title=None, orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=0, r=40, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabel + unduh
    st.subheader("Tabel ranking")
    st.dataframe(
        ranking[["Peringkat", "Kecamatan", "Skor", "Prioritas"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Skor": st.column_config.ProgressColumn(
                "Skor (Vi)", min_value=0, max_value=float(ranking["Skor"].max()), format="%.4f"
            )
        },
    )
    st.download_button(
        "Unduh ranking (CSV)",
        ranking.to_csv(index=False).encode("utf-8"),
        file_name="ranking_saw.csv",
        mime="text/csv",
    )

# =====================================================================
# TAB 2: TAHAPAN PERHITUNGAN SAW (transparansi)
# =====================================================================
with tab_tahapan:
    if simulasi:
        st.caption("Mode simulasi aktif: perhitungan di bawah memakai bobot simulasi.")

    tab_data, tab_mat, tab_bobot, tab_norm, tab_terbobot, tab_skor = st.tabs(
        ["1. Data mentah", "2. Matriks keputusan", "3. Bobot",
         "4. Normalisasi", "5. Matriks terbobot", "6. Skor akhir"]
    )

    with tab_data:
        st.write("Data input: jumlah kasus penyakit, penduduk, sarana, dan tenaga kesehatan.")
        st.dataframe(df, hide_index=True, use_container_width=True)

    with tab_mat:
        st.write("Nilai tiap kriteria dihitung dari data mentah:")
        st.latex(r"C_{1..4} = \frac{\text{jumlah kasus}}{\text{penduduk}} \times 1000")
        st.latex(r"C_5 = \frac{\text{penduduk}}{\text{sarana kesehatan}} \qquad C_6 = \frac{\text{penduduk}}{\text{tenaga kesehatan}}")
        st.dataframe(hasil["matriks"].round(2), use_container_width=True)

    with tab_bobot:
        st.write("Seluruh kriteria bertipe benefit (nilai makin besar, makin prioritas).")
        tabel_bobot = pd.DataFrame({
            "Kriteria": KRITERIA,
            "Nama": [NAMA_KRITERIA[k] for k in KRITERIA],
            "Jenis": "Benefit",
            "Bobot (%)": [bobot[k] * 100 for k in KRITERIA],
        })
        st.dataframe(
            tabel_bobot, hide_index=True, use_container_width=True,
            column_config={"Bobot (%)": st.column_config.NumberColumn(format="%.2f")},
        )
        st.caption(f"Total bobot: {sum(bobot.values()) * 100:.2f}%")

    with tab_norm:
        st.write("Normalisasi kriteria benefit dengan membagi nilai terhadap nilai maksimum kolomnya:")
        st.latex(r"r_{ij} = \frac{x_{ij}}{\max_i(x_{ij})}")
        st.write("Nilai maksimum tiap kriteria:")
        st.dataframe(hasil["matriks"].max().to_frame("Maksimum").T.round(2), use_container_width=True)
        st.dataframe(hasil["normalisasi"].round(4), use_container_width=True)

    with tab_terbobot:
        st.write("Nilai ternormalisasi dikalikan bobot kriterianya:")
        st.latex(r"v_{ij} = w_j \times r_{ij}")
        st.dataframe(hasil["terbobot"].round(4), use_container_width=True)

    with tab_skor:
        st.write("Skor akhir adalah jumlah nilai terbobot tiap kecamatan:")
        st.latex(r"V_i = \sum_{j=1}^{6} w_j \, r_{ij}")
        rincian = hasil["terbobot"].loc[hasil["ranking"].index].copy()
        rincian["Skor (Vi)"] = hasil["ranking"]["Skor"]
        rincian["Peringkat"] = hasil["ranking"]["Peringkat"]
        st.dataframe(
            rincian.round(4), use_container_width=True,
            column_config={"Peringkat": st.column_config.NumberColumn(format="%d")},
        )

# =====================================================================
# TAB 3: ANALISIS SENSITIVITAS BOBOT
# =====================================================================
with tab_sens:
    st.caption(
        "Ranking bobot ROC (resmi) dibandingkan dengan skenario bobot lain. "
        "Bagian ini tidak terpengaruh mode simulasi di sidebar."
    )

    with st.expander("Atur bobot skenario custom (%)"):
        default_custom = {"C1": 15, "C2": 15, "C3": 15, "C4": 15, "C5": 20, "C6": 20}
        kol = st.columns(3)
        for i, k in enumerate(KRITERIA):
            kol[i % 3].number_input(
                f"{k}", min_value=0.0, max_value=100.0, step=0.01,
                value=float(default_custom[k]), key=f"cw_{k}",
            )
        total_custom = sum(st.session_state[f"cw_{k}"] for k in KRITERIA)
        st.caption(f"Total: {total_custom:.2f}% (dinormalisasi otomatis jika bukan 100%)")

    if total_custom == 0:
        st.warning("Total bobot custom 0%. Isi minimal satu bobot.")
    else:
        skenario = {
            "ROC (resmi)": BOBOT_ROC,
            "Sama rata": {k: 1 / len(KRITERIA) for k in KRITERIA},
            "Custom": {k: st.session_state[f"cw_{k}"] / total_custom for k in KRITERIA},
        }
        peringkat = pd.DataFrame({
            nama: jalankan_saw(df, b)["ranking"]["Peringkat"] for nama, b in skenario.items()
        }).sort_values("ROC (resmi)")

        # Ringkasan kestabilan (Spearman = korelasi Pearson pada peringkat)
        korelasi = peringkat.corr()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prioritas #1 (ROC)", peringkat["ROC (resmi)"].idxmin(), border=True)
        m2.metric("Prioritas #1 (Sama rata)", peringkat["Sama rata"].idxmin(), border=True)
        m3.metric("Spearman ROC vs Sama rata", f"{korelasi.loc['ROC (resmi)', 'Sama rata']:.4f}", border=True)
        m4.metric("Spearman ROC vs Custom", f"{korelasi.loc['ROC (resmi)', 'Custom']:.4f}", border=True)

        # Bump chart
        panjang = peringkat.reset_index().melt(
            id_vars="Kecamatan", var_name="Skenario", value_name="Peringkat"
        )
        fig_bump = px.line(
            panjang, x="Skenario", y="Peringkat", color="Kecamatan", markers=True,
            category_orders={"Skenario": list(skenario.keys())},
        )
        fig_bump.update_yaxes(autorange="reversed", dtick=1)
        fig_bump.update_layout(height=600, xaxis_title=None)
        st.plotly_chart(fig_bump, use_container_width=True)

        # Tabel selisih peringkat
        tabel = peringkat.copy()
        tabel["Δ Sama rata"] = tabel["Sama rata"] - tabel["ROC (resmi)"]
        tabel["Δ Custom"] = tabel["Custom"] - tabel["ROC (resmi)"]
        st.write("Selisih peringkat terhadap ROC (positif = turun peringkat, negatif = naik):")
        st.dataframe(tabel, use_container_width=True)
        st.download_button(
            "Unduh perbandingan peringkat (CSV)",
            tabel.reset_index().to_csv(index=False).encode("utf-8"),
            file_name="sensitivitas_bobot.csv", mime="text/csv",
        )