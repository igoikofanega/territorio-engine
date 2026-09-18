"""Tests de la programación diaria. Sin daemon: se inspeccionan las definiciones.

Un schedule mal escrito no falla al cargar: falla a su hora, cuando nadie mira. Aquí se
exige que apunte a assets que existen y que las tandas que comparten cuota de LLM no se
pisen.
"""

from __future__ import annotations

import pytest

from territorio_pipelines.definitions import defs
from territorio_pipelines.schedules import SCHEDULES


def _por_nombre(nombre: str):
    return next(s for s in SCHEDULES if s.name == nombre)


def _assets(nombre: str) -> set[str]:
    """Assets que materializa el schedule, resueltos como los resuelve el daemon."""
    repo = defs.get_repository_def()
    job = repo.get_job(repo.get_schedule_def(nombre).job_name)
    return {k.to_user_string() for k in job.asset_layer.executable_asset_keys}


def _hora(schedule) -> tuple[int, int]:
    minuto, hora, *_ = schedule.cron_schedule.split()
    return int(hora), int(minuto)


@pytest.mark.parametrize("schedule", SCHEDULES, ids=lambda s: s.name)
def test_cada_schedule_apunta_a_assets_que_existen(schedule):
    """Una errata en el nombre del asset solo se descubriría a las 9:00 del día
    siguiente, en el historial de ejecuciones fallidas."""
    assert _assets(schedule.name), f"{schedule.name} no selecciona ningún asset"


def test_la_narrativa_tiene_tanda_diaria():
    """Se genera por tandas, como el etiquetado: la cuota gratuita no da para los 272
    informes de una vez, y cuando cambian los datos de un municipio hay que rehacerlo."""
    s = _por_nombre("narrativa_diaria")
    assert s.execution_timezone == "Europe/Madrid"
    assert _assets(s.name) == {"narrativa"}


def test_la_narrativa_corre_despues_del_etiquetado():
    """Comparten la cuota diaria del proveedor. Si arrancaran a la vez, cada una
    agotaría la mitad de la cuota de la otra."""
    assert _hora(_por_nombre("narrativa_diaria")) > _hora(_por_nombre("etiquetado_noticias"))
