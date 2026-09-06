"""Tests del golden set. Sin base de datos: se falsea `read_sql`.

Lo que se protege es la **estratificación**. La muestra existe para medir la extracción
también en los pueblos pequeños; si al recortarla se cuela un sesgo hacia los municipios
con más prensa —que son los grandes—, la métrica dejaría de decir lo que dice sin que
nada fallara.
"""

from __future__ import annotations

import pandas as pd
import pytest

from territorio_pipelines import golden


def _noticias(n_municipios: int, por_municipio: dict[str, int] | None = None) -> pd.DataFrame:
    """Municipios con muy distinta cantidad de prensa, como en la realidad."""
    filas = []
    for i in range(n_municipios):
        cod = f"31{i:03d}"
        cuantas = (por_municipio or {}).get(cod, 30)
        for j in range(cuantas):
            filas.append(
                {
                    "cod_municipio": cod,
                    "url_sha1": f"{i:03d}{j:037d}",
                    "municipio": f"Pueblo {i}",
                    "medio": "diariodenavarra.es",
                    "fecha": f"20{17 + j % 8}-01-01",
                    "titular": f"Titular {i}-{j}",
                }
            )
    return pd.DataFrame(filas)


@pytest.fixture
def sin_bd(monkeypatch):
    def _montar(df):
        monkeypatch.setattr(golden.pd, "read_sql", lambda *a, **k: df)

    return _montar


class TestMuestra:
    def test_toma_como_mucho_por_municipio(self, sin_bd):
        sin_bd(_noticias(5))
        m = golden.muestra(None, por_municipio=8, tope=0)
        assert (m.groupby("cod_municipio").size() <= 8).all()

    def test_respeta_el_tope(self, sin_bd):
        """Con 189 municipios cubiertos la muestra se iba a 1.303 filas, que no es
        etiquetable con cuidado por nadie."""
        sin_bd(_noticias(189))
        m = golden.muestra(None, por_municipio=8, tope=200)
        assert len(m) <= 200

    def test_al_recortar_sortea_municipios_enteros(self, sin_bd):
        """Recortar filas sueltas dejaría la muestra dominada por los municipios con más
        prensa. Los que entran tienen que entrar con su cuota completa."""
        sin_bd(_noticias(100))
        m = golden.muestra(None, por_municipio=8, tope=200)
        tam = m.groupby("cod_municipio").size()
        assert (tam == 8).all(), f"cuotas incompletas: {tam[tam != 8].to_dict()}"

    def test_no_se_queda_con_los_de_mas_prensa(self, sin_bd):
        """El sesgo que la estratificación existe para evitar: si el recorte se guiara por
        el volumen, solo entrarían los grandes."""
        cantidades = {f"31{i:03d}": (250 if i < 5 else 9) for i in range(100)}
        sin_bd(_noticias(100, cantidades))
        elegidos = set(golden.muestra(None, por_municipio=8, tope=200)["cod_municipio"])
        grandes = {f"31{i:03d}" for i in range(5)}
        assert not grandes <= elegidos, "entraron todos los municipios con más prensa"

    def test_es_reproducible(self, sin_bd):
        sin_bd(_noticias(100))
        a = golden.muestra(None, por_municipio=8, tope=200)
        sin_bd(_noticias(100))
        b = golden.muestra(None, por_municipio=8, tope=200)
        pd.testing.assert_frame_equal(a, b)

    def test_sin_noticias_no_revienta(self, sin_bd):
        columnas = ["cod_municipio", "url_sha1", "municipio", "medio", "fecha", "titular"]
        sin_bd(pd.DataFrame(columns=columnas))
        assert golden.muestra(None).empty

    def test_no_pide_mas_de_lo_que_hay(self, sin_bd):
        sin_bd(_noticias(3, {"31000": 2}))
        m = golden.muestra(None, por_municipio=8, tope=0)
        assert (m["cod_municipio"] == "31000").sum() == 2


class TestEtiquetasVersionadas:
    """El CSV de referencia se versiona; sin él `make golden-metricas` no corre."""

    def test_existe_y_tiene_las_columnas(self):
        from pathlib import Path

        csv = Path(__file__).resolve().parents[3] / "docs/golden/noticias-etiquetas.csv"
        assert csv.exists(), "falta docs/golden/noticias-etiquetas.csv"
        df = pd.read_csv(csv, dtype={"cod_municipio": str})
        assert set(golden.CAMPOS_ETIQUETAS) <= set(df.columns)
        assert len(df) > 100

    def test_los_codigos_conservan_los_ceros(self):
        from pathlib import Path

        csv = Path(__file__).resolve().parents[3] / "docs/golden/noticias-etiquetas.csv"
        df = pd.read_csv(csv, dtype={"cod_municipio": str})
        assert df["cod_municipio"].str.fullmatch(r"\d{5}").all()

    def test_no_lleva_texto_de_terceros(self):
        """El repositorio declara que no redistribuye datos: solo hash y juicio."""
        from pathlib import Path

        csv = Path(__file__).resolve().parents[3] / "docs/golden/noticias-etiquetas.csv"
        df = pd.read_csv(csv)
        assert "titular" not in df.columns and "medio" not in df.columns
