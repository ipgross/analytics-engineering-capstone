"""
NBA dbt Daily DAG (Cold Path)

Write-Audit-Publish pipeline for models that depend on events and/or
odds data, loaded by the ingestion DAGs at 7:00am ET. Cross-DAG
refs to rolling stats (built by nba_dbt_finalize at 3:02am ET)
are already materialized — Cosmos skips non-selected upstream models.

WAP flow: audit table (write) → tests (audit) → production merge (publish).
Cosmos TestBehavior.AFTER_EACH enforces the quality gate automatically.

Uses ExternalTaskSensors to wait for both events and odds DAGs to
complete before running dbt, replacing the implicit 2-minute timing gap.

Schedule: 7:02am ET (12:02 UTC)
Models: stg_nba__events+, stg_nba__odds_open+ (full descendant graph)
"""
import os
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import ShortCircuitOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, RenderConfig, ExecutionConfig
from cosmos.constants import TestBehavior
from dotenv import load_dotenv

from include.capstone.config import is_nba_season
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

# ===========================================
# Environment variables for dbt profiles.yml
# (.env is gitignored — credentials stay out of repo)
# ===========================================
airflow_home = os.environ.get("AIRFLOW_HOME", "")

load_dotenv(os.path.join(airflow_home, "dbt_project", ".env"), override=False)
load_dotenv(os.path.join(airflow_home, "dbt_project", "dbt.env"), override=False)

# Override private key path for deployment (.env has local Windows path)
os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"] = os.path.join(airflow_home, "rsa_key.p8")
os.environ["STUDENT_SCHEMA"] = "ipgross"

# ===========================================
# Cosmos / dbt configuration
# ===========================================
PATH_TO_DBT_PROJECT = os.path.join(airflow_home, "dbt_project")
PATH_TO_DBT_PROFILES = os.path.join(airflow_home, "dbt_project", "profiles.yml")

profile_config = ProfileConfig(
    profile_name="nba_betting_analytics",
    target_name="dev",
    profiles_yml_filepath=PATH_TO_DBT_PROFILES,
)

execution_config = ExecutionConfig(
    dbt_executable_path=os.path.join(airflow_home, "dbt_venv", "bin", "dbt"),
)


def check_season_today(**context):
    """Short-circuit if today (ds) is outside NBA season."""
    return is_nba_season(context["ds"])


@dag(
    dag_id="nba_dbt_daily_v3",
    description="dbt after ingestion: betting results, game results, predictions, grades",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=45),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="2 12 * * *",  # 7:02am ET = 12:02 UTC
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "dbt", "cold-path"],
)
def nba_dbt_daily():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=check_season_today,
    )

    # Wait for upstream ingestion DAGs instead of relying on 2-min timing gap.
    # execution_delta=2min because this DAG runs at :02 and upstream runs at :00.
    # allowed_states includes "skipped" so off-season short-circuits don't block.
    wait_for_events = ExternalTaskSensor(
        task_id="wait_for_events_dag",
        external_dag_id="nba_ingest_events_v3",
        external_task_id="log_ingestion",
        execution_delta=timedelta(minutes=2),
        allowed_states=["success", "skipped"],
        mode="reschedule",
        timeout=60 * 60 * 2,
        poke_interval=60,
    )

    wait_for_odds = ExternalTaskSensor(
        task_id="wait_for_odds_dag",
        external_dag_id="nba_ingest_odds_v3",
        external_task_id="log_ingestion",
        execution_delta=timedelta(minutes=2),
        allowed_states=["success", "skipped"],
        mode="reschedule",
        timeout=60 * 60 * 2,
        poke_interval=60,
    )

    dbt_tasks = DbtTaskGroup(
        group_id="dbt_nba_daily",
        project_config=ProjectConfig(PATH_TO_DBT_PROJECT),
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=RenderConfig(
            select=["stg_nba__events+", "stg_nba__odds_open+"],
            exclude=["path:models/nba/live"],
            test_behavior=TestBehavior.AFTER_EACH,
            emit_datasets=False,
        ),
    )

    post = EmptyOperator(task_id="post_dbt", trigger_rule="all_done")

    check >> [wait_for_events, wait_for_odds] >> dbt_tasks >> post


nba_dbt_daily()
