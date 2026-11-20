import pandas as pd

KOLOM_WAJIB = ["Kecamatan", "Penduduk", "TBC", "Pneumonia", "Diare", "DBD", "Fasilitas", "Tenaga"]
KOLOM_ANGKA = KOLOM_WAJIB[1:]

# Nama header alternatif yang tetap diterima
ALIAS_KOLOM = {
    "Jumlah Penduduk (jiwa)": "Penduduk",
    "Fasilitas Kesehatan": "Fasilitas",
    "Tenaga Kesehatan": "Tenaga",
}

TEMPLATE_CSV = (
    "Kecamatan,Penduduk,TBC,Pneumonia,Diare,DBD,Fasilitas,Tenaga\n"
    "Contoh A,70278,261,154,763,60,13,46\n"
    "Contoh B,86989,242,31,574,57,15,277\n"
    "Contoh C,97535,439,207,1600,58,15,799\n"
).encode("utf-8")


def baca_dan_validasi(sumber):
    """Baca CSV (path atau file upload). Kembalikan (df, daftar_error)."""
    if hasattr(sumber, "seek"):
        sumber.seek(0)
    try:
        df = pd.read_csv(sumber, sep=None, engine="python", encoding="utf-8-sig")
    except Exception as e:
        return None, [f"File tidak bisa dibaca sebagai CSV ({e})."]

    df.columns = df.columns.astype(str).str.strip()
    df = df.rename(columns=ALIAS_KOLOM)

    hilang = [k for k in KOLOM_WAJIB if k not in df.columns]
    if hilang:
        return None, [
            f"Kolom wajib tidak ditemukan: {', '.join(hilang)}. "
            f"Kolom yang terbaca: {', '.join(df.columns)}."
        ]

    errors = []
    df = df[KOLOM_WAJIB].dropna(how="all").copy()

    if df["Kecamatan"].isna().any():
        errors.append("Ada baris dengan nama kecamatan kosong.")
    df["Kecamatan"] = df["Kecamatan"].astype(str).str.strip()

    if df["Kecamatan"].duplicated().any():
        dobel = df.loc[df["Kecamatan"].duplicated(), "Kecamatan"].tolist()
        errors.append(f"Nama kecamatan ganda: {', '.join(dobel)}.")

    # Konversi ke angka (titik pada kolom teks dianggap pemisah ribuan)
    for k in KOLOM_ANGKA:
        kolom = df[k]
        if kolom.dtype == object:
            kolom = kolom.astype(str).str.strip().str.replace(".", "", regex=False)
        df[k] = pd.to_numeric(kolom, errors="coerce")

    for k in KOLOM_ANGKA:
        baris = df.loc[df[k].isna(), "Kecamatan"].tolist()
        if baris:
            errors.append(f"Kolom {k}: nilai kosong/bukan angka pada {', '.join(baris[:5])}.")
        if (df[k] < 0).any():
            errors.append(f"Kolom {k}: ada nilai negatif.")

    for k in ["Penduduk", "Fasilitas", "Tenaga"]:
        if (df[k] <= 0).any():
            errors.append(f"Kolom {k}: harus lebih dari 0 (dipakai sebagai pembagi).")

    if df["Penduduk"].max() < 1000:
        errors.append(
            "Nilai Penduduk tampak terlalu kecil. Periksa apakah titik ribuan "
            "(70.278) terbaca sebagai desimal; tulis tanpa titik (70278)."
        )

    if len(df) < 3:
        errors.append("Minimal 3 kecamatan diperlukan.")

    return (None if errors else df.reset_index(drop=True)), errors