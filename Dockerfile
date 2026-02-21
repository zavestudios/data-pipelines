FROM python:3.11-slim

WORKDIR /app

ARG AIRFLOW_VERSION=2.9.3          
ARG PYTHON_VERSION=3.11            
ARG AIRFLOW_CONSTRAINTS_URL=https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip && \             
    python -m pip install --no-cache-dir -c "${AIRFLOW_CONSTRAINTS_URL}" -r requirements.txt

RUN addgroup --system etl && adduser --system --ingroup etl etl

COPY etl/ ./etl/
COPY scripts/ ./scripts/
COPY dags/ ./dags/

USER etl

ENTRYPOINT ["python"]
