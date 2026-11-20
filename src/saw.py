import pandas as pd

KRITERIA = ["C1", "C2", "C3", "C4", "C5", "C6"]

NAMA_KRITERIA = {
    "C1": "TB Paru per 1.000 penduduk",
    "C2": "Pneumonia per 1.000 penduduk",
    "C3": "Diare per 1.000 penduduk",
    "C4": "DBD per 1.000 penduduk",
    "C5": "Penduduk per sarana kesehatan",
    "C6": "Penduduk per tenaga kesehatan",
}

def roc(n: int) -> list[float]:
    """Bobot ROC untuk n elemen yang sudah diurutkan dari paling penting."""
    return [sum(1 / i for i in range(k, n + 1)) / n for k in range(1, n + 1)]


# Urutan kepentingan (paling penting di depan)
URUTAN_KELOMPOK = ["Beban penyakit", "Ketersediaan layanan"]
URUTAN_DALAM_KELOMPOK = {
    "Beban penyakit": ["C1", "C3", "C4", "C2"],
    "Ketersediaan layanan": ["C6", "C5"],
}


def hitung_bobot_roc_berjenjang(urutan_kelompok, urutan_dalam) -> dict:
    """Bobot akhir = bobot kelompok x bobot ROC di dalam kelompok."""
    bobot = {}
    bobot_kelompok = roc(len(urutan_kelompok))
    for kelompok, w_kel in zip(urutan_kelompok, bobot_kelompok):
        kriteria = urutan_dalam[kelompok]
        for k, w_dalam in zip(kriteria, roc(len(kriteria))):
            bobot[k] = w_kel * w_dalam
    return {k: bobot[k] for k in sorted(bobot)}  # urut C1..C6


BOBOT_ROC = hitung_bobot_roc_berjenjang(URUTAN_KELOMPOK, URUTAN_DALAM_KELOMPOK)


def hitung_matriks_keputusan(df: pd.DataFrame) -> pd.DataFrame:
    """Data mentah -> nilai kriteria C1..C6 per kecamatan."""
    d = df.set_index("Kecamatan")
    m = pd.DataFrame(index=d.index)
    m["C1"] = d["TBC"] / d["Penduduk"] * 1000
    m["C2"] = d["Pneumonia"] / d["Penduduk"] * 1000
    m["C3"] = d["Diare"] / d["Penduduk"] * 1000
    m["C4"] = d["DBD"] / d["Penduduk"] * 1000
    m["C5"] = d["Penduduk"] / d["Fasilitas"]
    m["C6"] = d["Penduduk"] / d["Tenaga"]
    return m


def normalisasi(matriks: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi min-max untuk kriteria benefit: r = (x - min) / (max - min)."""
    rentang = (matriks.max() - matriks.min()).replace(0, 1)
    return (matriks - matriks.min()) / rentang


def hitung_terbobot(r: pd.DataFrame, bobot: dict) -> pd.DataFrame:
    """Kalikan tiap kolom ternormalisasi dengan bobotnya."""
    return r * pd.Series(bobot)


def hitung_ranking(terbobot: pd.DataFrame) -> pd.DataFrame:
    """Jumlahkan baris -> skor Vi, lalu urutkan dari terbesar."""
    hasil = terbobot.sum(axis=1).rename("Skor").to_frame()
    hasil = hasil.sort_values("Skor", ascending=False)
    hasil["Peringkat"] = range(1, len(hasil) + 1)
    return hasil


def jalankan_saw(df: pd.DataFrame, bobot: dict | None = None) -> dict:
    """Jalankan seluruh tahapan SAW, kembalikan tiap tahap."""
    bobot = bobot or BOBOT_ROC
    matriks = hitung_matriks_keputusan(df)
    r = normalisasi(matriks)
    terbobot = hitung_terbobot(r, bobot)
    ranking = hitung_ranking(terbobot)
    return {
        "matriks": matriks,
        "normalisasi": r,
        "terbobot": terbobot,
        "ranking": ranking,
    }