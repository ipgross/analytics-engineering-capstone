"""
NBA dbt Finalize DAG (Cold Path)

Write-Audit-Publish pipeline for models that depend on games + box
scores + teams data, loaded by the nba_finalize_games DAG.
Excludes models that also depend on events/odds (those run in
nba_dbt_daily).

WAP flow: audit table (write) → tests (audit) → production merge (publish).
Cosmos TestBehavior.AFTER_EACH enforces the quality gate automatically.

Supports two trigger modes:
  - Scheduled (3:02am ET): safety-net run, uses ds-1 for season check
  - Event-triggered: fired by nba_finalize_games via TriggerDagRunOperator
    when a game goes Final; accepts game_date via dag_run.conf

Schedule: 3:02am ET (08:02 UTC) + event-triggered by nba_finalize_games
Models: stg_nba__games+, stg_nba__player_box_scores+, stg_nba__teams+
        minus stg_nba__events+, stg_nba__odds_open+ (DAG 2)
"""
import os
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import ShortCircuitOperator
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


def check_season(**context):
    """Short-circuit if game_date is outside NBA season.

    Event-triggered runs pass game_date via conf from nba_finalize_games.
    Scheduled runs fall back to ds-1 (yesterday's completed games).
    """
    dag_run = context.get("dag_run")
    if dag_run and getattr(dag_run, "conf", None) and dag_run.conf.get("game_date"):
        game_date = dag_run.conf["game_date"]
    else:
        ds = context["ds"]
        game_date = (datetime.strptime(ds, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    return is_nba_season(game_date)


@dag(
    dag_id="nba_dbt_finalize_v3",
    description="dbt after finalize: team stats, rolling averages, matchup stats",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=45),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="2 8 * * *",  # 3:02am ET = 08:02 UTC
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "dbt", "cold-path"],
)
def nba_dbt_finalize():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=check_season,
    )

    dbt_tasks = DbtTaskGroup(
        group_id="dbt_nba_finalize",
        project_config=ProjectConfig(PATH_TO_DBT_PROJECT),
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=RenderConfig(
            select=["stg_nba__games+", "stg_nba__player_box_scores+", "stg_nba__teams+"],
            exclude=["stg_nba__events+", "stg_nba__odds_open+", "path:models/nba/live"],
            test_behavior=TestBehavior.AFTER_EACH,
            emit_datasets=False,
        ),
    )

    post = EmptyOperator(task_id="post_dbt", trigger_rule="all_done")

    check >> dbt_tasks >> post


nba_dbt_finalize()
