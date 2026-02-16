# NBA Spread-Beating Analytics Pipeline

End-to-end architecture: two external APIs feed a hot/cold dual-path Airflow pipeline on Astronomer, transforming data through dbt into Snowflake, and serving a Streamlit dashboard for spread cover analysis.

```mermaid
flowchart TD
    subgraph sources["External Data Sources"]
        ODDS["The Odds API\n<i>Betting lines: h2h, spreads, totals</i>\n<i>6 bookmakers &bull; 3 markets</i>"]
        BDL["BallDontLie API\n<i>Scores, box scores, play-by-play</i>\n<i>30 NBA teams</i>"]
    end

    subgraph airflow["Airflow on Astronomer &mdash; 9 DAGs"]
        direction LR
        subgraph cold_dags["Cold Path DAGs (daily batch)"]
            direction TB
            IE["Ingest Events\n<i>7am ET</i>"]
            IO["Ingest Odds\n<i>7am ET</i>"]
            IU["Ingest Upcoming\n<i>8am ET, 7-day ahead</i>"]
            FG["Finalize Games\n<i>3am ET + triggered</i>"]
            DD["dbt Daily\n<i>7:02am ET</i>"]
            DF["dbt Finalize\n<i>3:02am ET + triggered</i>"]
            DR["dbt Full Refresh\n<i>manual</i>"]
        end
        subgraph hot_dags["Hot Path DAGs (live)"]
            direction TB
            LS["Live Scoreboard\n<i>every 1 min</i>"]
            LO["Live Odds\n<i>every 5 min</i>"]
        end
        GATE["is_nba_season() + is_game_window()\n<i>ShortCircuit gating</i>"]
    end

    subgraph s3["AWS S3"]
        ARC["archive/\n<i>Raw JSON.gz</i>"]
        BLK["bulk/\n<i>Typed Parquet</i>"]
    end

    subgraph snowflake["Snowflake (ipgross schema)"]
        direction TB
        subgraph cold_tables["Cold Path Tables"]
            STG["stg_nba_*\n<i>Transient staging</i>"]
            HIST["hist_nba_*\n<i>Production tables</i>\n<i>events, odds, games,\nbox scores, teams</i>"]
        end
        subgraph hot_tables["Hot Path Tables"]
            LIVE["live_nba_*\n<i>scoreboard, odds,\nbox scores, plays</i>"]
            SNAP["archive_nba_odds_snapshots\n<i>Append-only</i>"]
        end
        OPS["ops_ingestion_runs\n<i>Audit metadata</i>"]
    end

    subgraph dbt_layer["dbt (Cosmos WAP Pipeline)"]
        direction LR
        DBT_STG["Staging\n<i>views: rename,\ncoalesce, dedup</i>"]
        DBT_INT["Intermediate\n<i>incremental: team stats,\nconsensus lines,\nrolling averages</i>"]
        DBT_MRT["Marts\n<i>game results,\nATS records,\npredictions,\ngame grades</i>"]
        DBT_LV["Live Views\n<i>scoreboard,\nodds current,\nodds movement,\ngame detail</i>"]
    end

    DASH["THE COVER\nStreamlit Dashboard\n<i>Live scores, predictions,\nodds, grades, records,\nmatchup analysis</i>"]

    %% Source to Airflow
    ODDS -->|"events + odds"| cold_dags
    BDL -->|"scores + stats"| cold_dags
    ODDS -->|"live odds"| hot_dags
    BDL -->|"live scores + plays"| hot_dags

    %% Gating
    GATE -.->|"gates all DAGs"| cold_dags
    GATE -.->|"gates hot path"| hot_dags

    %% Cold path flow
    cold_dags -->|"raw JSON.gz"| ARC
    cold_dags -->|"typed Parquet"| BLK
    BLK -->|"COPY INTO\n(FORCE=TRUE)"| STG
    STG -->|"DQ checks\nthen MERGE"| HIST
    cold_dags -->|"log runs"| OPS

    %% Hot path flow
    hot_dags -->|"MERGE FROM\nVALUES"| LIVE
    LO -->|"snapshot"| SNAP

    %% Convergence
    LS -->|"detect Final\ntrigger finalize"| FG
    FG -->|"trigger"| DF

    %% DAG coordination
    IE -->|"ExternalTaskSensor"| DD
    IO -->|"ExternalTaskSensor"| DD

    %% dbt flow
    HIST --> DBT_STG
    DBT_STG --> DBT_INT
    DBT_INT --> DBT_MRT
    LIVE --> DBT_LV
    DBT_INT -.->|"cold baselines\nfor live grades"| DBT_LV

    %% Dashboard
    DBT_MRT -->|"query"| DASH
    DBT_LV -->|"query"| DASH

    %% Styles
    style sources fill:#f0f4ff,stroke:#4a6fa5,stroke-width:2px
    style cold_dags fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style hot_dags fill:#fbe9e7,stroke:#bf360c,stroke-width:2px
    style airflow fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style s3 fill:#f5f5f5,stroke:#616161,stroke-width:2px
    style snowflake fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style cold_tables fill:#e8f5e9,stroke:#2e7d32
    style hot_tables fill:#fbe9e7,stroke:#bf360c
    style dbt_layer fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    style DASH fill:#fce4ec,stroke:#c62828,stroke-width:2px
    style GATE fill:#f3e5f5,stroke:#6a1b9a
```

**Legend:** Blue = cold path (daily batch) | Orange/Red = hot path (live) | Green = Snowflake | Yellow = dbt | Pink = dashboard

**Key flows:**
- **Cold path:** APIs → Airflow (7am/3am ET) → S3 archive + Parquet → Snowflake staging → DQ validation → MERGE into `hist_nba_*` → dbt WAP → marts
- **Hot path:** APIs → Airflow (1-5 min) → Python validation → `MERGE FROM VALUES` into `live_nba_*` → dbt live views
- **Convergence:** Live scoreboard detects game Final → triggers cold-path finalize → dbt rebuild (~10-20 min)
- **Dashboard:** Streamlit queries both mart tables (predictions, grades, records) and live views (scoreboard, odds)
