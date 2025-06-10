FROM python:3.12-slim AS base

WORKDIR /app

# Installiere System-Abhängigkeiten
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Installiere Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere die gesamte Anwendung
COPY /app /app

EXPOSE 8000

ENTRYPOINT [ "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000" ]