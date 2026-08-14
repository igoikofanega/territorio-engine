# Qué cambia

<!-- Una o dos frases. Si hay un issue, enlázalo con "Closes #N". -->

## Por qué

<!-- El problema que resuelve. Si es una fuente nueva o un modelo nuevo, di qué
     pregunta permite responder que antes no se podía. -->

## Cómo verificarlo

<!-- Los comandos exactos. Recuerda que el rebuild es por servicio:
     docker compose up --build -d api -->

```bash

```

## Comprobaciones

- [ ] `make lint` pasa
- [ ] `make test` pasa **sin red y sin API keys**
- [ ] Si toca la BD: hay migración Alembic **y** `models.py` está sincronizado
- [ ] Si añade una fuente: el crudo aterriza en `raw/` antes de transformar, y
      la fuente está en `NOTICE` con su licencia
- [ ] Si añade datos estimados, imputados o enmascarados: están marcados como
      tales y no se presentan como medidos
- [ ] Si toca el modelo: las métricas del backtest se han reejecutado y están
      en MLflow

## Notas para quien revise

<!-- Decisiones discutibles, alternativas descartadas, deuda que asumes a
     conciencia. Es más útil que decir que todo está bien. -->
