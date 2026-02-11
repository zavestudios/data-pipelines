import os

import pytest

airflow = pytest.importorskip("airflow.models")
DagBag = airflow.DagBag


def test_listings_dag_loads() -> None:
    dags_path = os.path.join(os.getcwd(), "dags")
    dag_bag = DagBag(dag_folder=dags_path, include_examples=False)

    assert "listings_ingest" in dag_bag.dags
    assert dag_bag.import_errors == {}
