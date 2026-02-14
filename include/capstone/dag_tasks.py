"""
Cold-path DAG task factory.

Generates the standard stage → DQ → merge → log task chain used by all
cold-path DAGs (events, odds, reconcile). Each DAG provides dataset-specific
functions; the factory handles the boilerplate.

Usage:
    from include.capstone.dag_tasks import build_cold_path_tasks

    tasks = build_cold_path_tasks(
        dataset="events",
        dag_id=DAG_ID,
        game_date_fn=_game_date,
        fetch_task_id="fetch_events",
        stage_fn=stage_events,
        validate_fn=validate_events,
        merge_fn=merge_events,
    )
    # Wire: fetch >> [archive, bulk] >> tasks.stage >> tasks.dq >> tasks.merge >> tasks.log
"""
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from airflow.providers.standard.operators.python import PythonOperator

from include.capstone.database import classify_empty, log_ingestion_run

logger = logging.getLogger(__name__)


@dataclass
class ColdPathTasks:
    """Container for the generated task chain: stage → dq → merge → log."""
    stage: PythonOperator
    dq: PythonOperator
    merge: PythonOperator
    log: PythonOperator


def build_cold_path_tasks(
    dataset: str,
    dag_id: str,
    game_date_fn: Callable,
    fetch_task_id: str,
    stage_fn: Callable,
    validate_fn: Callable,
    merge_fn: Callable,
    empty_raise: bool = False,
    task_id_prefix: Optional[str] = None,
) -> ColdPathTasks:
    """Build standard stage → DQ → merge → log tasks for a cold-path dataset.

    Args:
        dataset: Dataset name for ops logging (e.g., "events", "odds_open", "games")
        dag_id: DAG ID for ops logging
        game_date_fn: Function(context) -> str that extracts game_date
        fetch_task_id: Task ID of the upstream fetch task (for XCom pull)
        stage_fn: Function(date_str, bulk_path) -> dict with staging logic
        validate_fn: Function(date_str) -> None that runs DQ checks
        merge_fn: Function(date_str) -> dict with merge logic
        empty_raise: If True, raise on EMPTY_UNEXPECTED (reconcile behavior)
        task_id_prefix: Optional prefix for task IDs (e.g., "games" -> "stage_games")

    Returns:
        ColdPathTasks with the four PythonOperator tasks, already chained.
    """
    prefix = f"{task_id_prefix}_" if task_id_prefix else ""
    bulk_task_id = f"upload_{task_id_prefix}_bulk" if task_id_prefix else "upload_bulk"

    def _run_stage(**context):
        ti = context["ti"]
        game_date = game_date_fn(context)
        bulk_path = ti.xcom_pull(task_ids=bulk_task_id)
        records = ti.xcom_pull(task_ids=fetch_task_id)

        if not records:
            status = classify_empty(game_date, dataset)
            log_ingestion_run(game_date, dataset, dag_id, status, rows_merged=0)
            print(f"Empty {dataset} for {game_date}: {status}")
            if empty_raise and status == "EMPTY_UNEXPECTED":
                raise ValueError(f"EMPTY_UNEXPECTED: events exist for {game_date} but 0 {dataset} returned")
            return {"ds": game_date, "staged": 0, "status": status}

        result = stage_fn(game_date, bulk_path)
        print(f"Stage {dataset} result: {result}")
        return result

    def _run_dq(**context):
        ti = context["ti"]
        game_date = game_date_fn(context)
        stage_result = ti.xcom_pull(task_ids=f"{prefix}stage" if prefix else "stage")
        if stage_result.get("staged", 0) == 0:
            print(f"Skipping {dataset} DQ — no staged data for {game_date}")
            return
        validate_fn(game_date)

    def _run_merge(**context):
        ti = context["ti"]
        game_date = game_date_fn(context)
        stage_result = ti.xcom_pull(task_ids=f"{prefix}stage" if prefix else "stage")
        if stage_result.get("staged", 0) == 0:
            print(f"Skipping {dataset} merge — no staged data for {game_date}")
            return {"ds": game_date, "merged": 0}
        result = merge_fn(game_date)
        print(f"Merge {dataset} result: {result}")
        return result

    def _run_log(**context):
        ti = context["ti"]
        game_date = game_date_fn(context)
        stage_result = ti.xcom_pull(task_ids=f"{prefix}stage" if prefix else "stage")

        if stage_result.get("status"):
            return

        merge_result = ti.xcom_pull(task_ids=f"{prefix}merge" if prefix else "merge") or {}
        archive_task = f"upload_{task_id_prefix}_archive" if task_id_prefix else "upload_archive"
        archive_path = ti.xcom_pull(task_ids=archive_task)
        bulk_path = ti.xcom_pull(task_ids=bulk_task_id)

        log_ingestion_run(
            date_str=game_date,
            dataset=dataset,
            dag_id=dag_id,
            status="SUCCESS",
            rows_merged=merge_result.get("merged", 0),
            s3_archive_path=archive_path,
            s3_bulk_path=bulk_path,
        )

    stage_task = PythonOperator(
        task_id=f"{prefix}stage" if prefix else "stage",
        python_callable=_run_stage,
    )
    dq_task = PythonOperator(
        task_id=f"{prefix}dq" if prefix else "dq_check",
        python_callable=_run_dq,
    )
    merge_task = PythonOperator(
        task_id=f"{prefix}merge" if prefix else "merge",
        python_callable=_run_merge,
    )
    log_task = PythonOperator(
        task_id=f"{prefix}log" if prefix else "log_ingestion",
        python_callable=_run_log,
    )

    # Wire the chain
    stage_task >> dq_task >> merge_task >> log_task

    return ColdPathTasks(
        stage=stage_task,
        dq=dq_task,
        merge=merge_task,
        log=log_task,
    )
