FROM python:3.12-slim

RUN pip install --no-cache-dir "mlflow>=2.17,<3"

EXPOSE 5000
# Backend en SQLite + artefactos servidos por el propio servidor (proxied artifacts),
# ambos en el volumen /mlflow para persistencia.
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", \
     "--backend-store-uri", "sqlite:////mlflow/mlflow.db", \
     "--artifacts-destination", "/mlflow/artifacts", "--serve-artifacts"]
