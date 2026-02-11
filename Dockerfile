FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system etl && adduser --system --ingroup etl etl

COPY etl/ ./etl/
COPY scripts/ ./scripts/
COPY dags/ ./dags/

USER etl

ENTRYPOINT ["python"]
