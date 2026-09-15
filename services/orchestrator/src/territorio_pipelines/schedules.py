"""Programación de los assets que no se pueden hacer de una sentada.

Hay trabajo que no cabe en una ejecución: el etiquetado de titulares son ~545 peticiones
a un proveedor con cuota gratuita por minuto **y por día**. Intentarlo del tirón no falla
elegantemente, falla a media faena.

La respuesta no es un `cron` en la máquina llamando a `docker compose run`. Eso deja el
trabajo fuera del orquestador: sin historial, sin logs consultables, sin reintentos y sin
forma de saber desde la interfaz si anoche corrió. Dagster ya trae planificación, y su
daemon está levantado con `dagster dev`, así que el schedule vive aquí y se ve en el
mismo sitio que todo lo demás.

Lo que hace que esto funcione sin vigilancia es que el asset es **incremental**: etiqueta
solo lo que no tiene modelo y no hace nada cuando ya no queda nada. Así la programación
diaria no necesita saber cuántas tandas van ni cuándo terminar — se apaga sola.
"""

from __future__ import annotations

from dagster import AssetSelection, DefaultScheduleStatus, ScheduleDefinition

#: Tanda diaria de etiquetado. A las 9:00 de Madrid, no UTC: las cuotas diarias de los
#: proveedores se reinician a medianoche del Pacífico, así que a esta hora la del día ya
#: está entera disponible.
etiquetado_noticias = ScheduleDefinition(
    name="etiquetado_noticias",
    cron_schedule="0 9 * * *",
    execution_timezone="Europe/Madrid",
    target=AssetSelection.assets("noticias_etiquetadas"),
    default_status=DefaultScheduleStatus.RUNNING,
    description=(
        "Etiqueta una tanda diaria de titulares con el LLM. Incremental: continúa donde "
        "quedó la anterior y se convierte en un no-op cuando no quedan pendientes."
    ),
)

SCHEDULES = [etiquetado_noticias]
