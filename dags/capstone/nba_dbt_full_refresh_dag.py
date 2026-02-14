"""
NBA dbt Full Refresh DAG (Manual)

Runs all cold-path dbt models with --full-refresh. Use for:
- First deployment (initial build of all tables)
- Recovery after schema changes or data issues
- Rebuilding incremental models from scratch

Uses Cosmos DbtTaskGroup for full dbt lineage in the Airflow UI.

Schedule: Manual trigger only
Models: All staging + intermediate + marts (excludes live views)
"""
import os
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.operators.empty import EmptyOperator
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, RenderConfig, ExecutionConfig
from cosmos.constants import TestBehavior
from dotenv import load_dotenv

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


@dag(
    dag_id="nba_dbt_full_refresh_v3",
    description="Manual: full-refresh all dbt NBA models (first deploy or recovery)",
    default_args={
        "owner": "capstone",
        "retries": 0,
        "execution_timeout": timedelta(hours=2),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "dbt", "manual"],
)
def nba_dbt_full_refresh():
    dbt_tasks = DbtTaskGroup(
        group_id="dbt_nba_full_refresh",
        project_config=ProjectConfig(PATH_TO_DBT_PROJECT),
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=RenderConfig(
            exclude=["path:models/nba/live"],
            test_behavior=TestBehavior.AFTER_EACH,
            emit_datasets=False,
        ),
        operator_args={"full_refresh": True},
    )

    post = EmptyOperator(task_id="post_dbt", trigger_rule="all_done")

    dbt_tasks >> post


nba_dbt_full_refresh()
