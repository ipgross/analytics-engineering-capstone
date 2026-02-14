"""
Snowflake connection and stage setup utilities.
"""
import logging

import snowflake.connector

from include.capstone.config import (
    SNOWFLAKE_ACCOUNT,
    SNOWFLAKE_USER,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_WAREHOUSE,
    SNOWFLAKE_DATABASE,
    SNOWFLAKE_ROLE,
    STUDENT_SCHEMA,
    S3_BULK_PREFIX,
)

logger = logging.getLogger(__name__)


def get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Create Snowflake connection using hardcoded credentials."""
    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=STUDENT_SCHEMA,
        role=SNOWFLAKE_ROLE,
    )


def _setup_parquet_stage(cursor, stage_name: str, dataset: str) -> str:
    """Create Parquet file format and external stage pointing to S3 bulk path."""
    from airflow.sdk import Variable

    aws_key = Variable.get("DATAEXPERT_AWS_ACCESS_KEY_ID")
    aws_secret = Variable.get("DATAEXPERT_AWS_SECRET_ACCESS_KEY")
    bucket = Variable.get("AWS_S3_BUCKET_TABULAR")

    format_name = f"{STUDENT_SCHEMA}.{dataset}_parquet_fmt"
    stage_url = f"s3://{bucket}/{S3_BULK_PREFIX}/{dataset}/"

    cursor.execute(f"""
        CREATE OR REPLACE FILE FORMAT {format_name}
        TYPE = PARQUET
    """)

    cursor.execute(f"""
        CREATE OR REPLACE STAGE {stage_name}
        URL = '{stage_url}'
        CREDENTIALS = (
            AWS_KEY_ID = '{aws_key}'
            AWS_SECRET_KEY = '{aws_secret}'
        )
        FILE_FORMAT = {format_name}
    """)

    logger.info(f"Created stage {stage_name} -> {stage_url}")
    return format_name
