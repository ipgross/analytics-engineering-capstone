"""
Airflow callback functions for failure alerting and task lifecycle events.

Applied via default_args['on_failure_callback'] in all capstone DAGs.
Currently logs structured failure details; extensible to Slack/email/PagerDuty.
"""
import logging

logger = logging.getLogger(__name__)


def alert_on_failure(context):
    """Log structured failure details when a task fails.

    Applied to all DAGs via default_args. Provides consistent failure
    logging across all cold-path and hot-path DAGs.

    Future: send to Slack webhook, email, or PagerDuty.
    """
    ti = context.get("task_instance")
    exception = context.get("exception")
    ds = context.get("ds", "unknown")

    dag_id = ti.dag_id if ti else "unknown"
    task_id = ti.task_id if ti else "unknown"
    try_number = ti.try_number if ti else 0
    max_tries = ti.max_tries if ti else 0
    log_url = ti.log_url if ti else ""

    logger.error(
        f"TASK_FAILED | dag={dag_id} | task={task_id} | ds={ds} "
        f"| try={try_number}/{max_tries} | error={exception}"
    )

    # Log URL for quick access in Airflow UI
    if log_url:
        logger.error(f"TASK_FAILED | log_url={log_url}")


def alert_on_dag_failure(context):
    """Log when an entire DAG run fails (all retries exhausted).

    Applied via on_failure_callback at the DAG level.
    """
    dag_run = context.get("dag_run")
    ds = context.get("ds", "unknown")

    dag_id = dag_run.dag_id if dag_run else "unknown"
    run_id = dag_run.run_id if dag_run else "unknown"

    # Collect all failed task IDs
    failed_tasks = []
    if dag_run:
        for ti in dag_run.get_task_instances():
            if ti.state == "failed":
                failed_tasks.append(ti.task_id)

    logger.error(
        f"DAG_FAILED | dag={dag_id} | ds={ds} | run_id={run_id} "
        f"| failed_tasks={failed_tasks}"
    )
