-- ================================================
-- Ops Metadata Table DDL
-- Tracks every ingestion run for audit, debugging, and DAG 2 gating.
-- ================================================

USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

CREATE TABLE IF NOT EXISTS ipgross.ops_ingestion_runs (
    run_id          INTEGER AUTOINCREMENT,
    ds              DATE NOT NULL,
    dataset         VARCHAR(50) NOT NULL,
    dag_id          VARCHAR(100),
    status          VARCHAR(20) NOT NULL,
    rows_merged     INTEGER DEFAULT 0,
    s3_archive_path VARCHAR(500),
    s3_bulk_path    VARCHAR(500),
    elapsed_sec     FLOAT,
    error_message   VARCHAR(2000),
    ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (run_id)
);

-- Verify table created
SHOW TABLES LIKE 'ops_%' IN SCHEMA ipgross;
