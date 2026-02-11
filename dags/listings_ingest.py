from __future__ import annotations

import os

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from kubernetes.client import models as k8s


NAMESPACE = os.getenv("AIRFLOW_RUN_NAMESPACE", "airflow")
ETL_IMAGE = os.getenv("ETL_IMAGE", "zavestudios/etl-runner:0.1.0")
INPUT_PATH = os.getenv("ETL_INPUT_PATH", "/data/listings.csv")
EXECUTION_BACKEND = os.getenv("ETL_EXECUTION_BACKEND", "kubernetes")


def _job_args(stage: str) -> list[str]:
    return [
        "-m",
        "etl.jobs.ingest_csv",
        "--input",
        INPUT_PATH,
        "--run-date",
        "{{ ds }}",
        "--batch-id",
        "{{ dag_run.run_id if dag_run else ts_nodash }}",
        "--stage",
        stage,
    ]


def _local_command(stage: str) -> str:
    return (
        "python -m etl.jobs.ingest_csv "
        f"--input {INPUT_PATH} "
        "--run-date '{{ ds }}' "
        "--batch-id '{{ dag_run.run_id if dag_run else ts_nodash }}' "
        f"--stage {stage}"
    )


with DAG(
    dag_id="listings_ingest",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
    tags=["etl", "kubernetes"],
) as dag:
    if EXECUTION_BACKEND == "local":
        extract_validate = BashOperator(
            task_id="extract_validate",
            bash_command=_local_command("extract_validate"),
        )
        load_postgres = BashOperator(
            task_id="load_postgres",
            bash_command=_local_command("load_postgres"),
        )
        dq_assertions = BashOperator(
            task_id="dq_assertions",
            bash_command=_local_command("dq_assertions"),
        )
    else:
        extract_validate = KubernetesPodOperator(
            task_id="extract_validate",
            name="extract-validate",
            namespace=NAMESPACE,
            image=ETL_IMAGE,
            cmds=["python"],
            arguments=_job_args("extract_validate"),
            in_cluster=True,
            is_delete_operator_pod=True,
            get_logs=True,
            do_xcom_push=False,
            container_resources=k8s.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "500m", "memory": "512Mi"},
            ),
        )

        load_postgres = KubernetesPodOperator(
            task_id="load_postgres",
            name="load-postgres",
            namespace=NAMESPACE,
            image=ETL_IMAGE,
            cmds=["python"],
            arguments=_job_args("load_postgres"),
            in_cluster=True,
            is_delete_operator_pod=True,
            get_logs=True,
            do_xcom_push=False,
            container_resources=k8s.V1ResourceRequirements(
                requests={"cpu": "150m", "memory": "256Mi"},
                limits={"cpu": "1000m", "memory": "1Gi"},
            ),
        )

        dq_assertions = KubernetesPodOperator(
            task_id="dq_assertions",
            name="dq-assertions",
            namespace=NAMESPACE,
            image=ETL_IMAGE,
            cmds=["python"],
            arguments=_job_args("dq_assertions"),
            in_cluster=True,
            is_delete_operator_pod=True,
            get_logs=True,
            do_xcom_push=False,
            container_resources=k8s.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "500m", "memory": "512Mi"},
            ),
        )

    extract_validate >> load_postgres >> dq_assertions
