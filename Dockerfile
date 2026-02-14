FROM astrocrpublic.azurecr.io/runtime:3.1-9

ENV PYTHONPATH="/usr/local/airflow:${PYTHONPATH}"

# dbt profile env vars (needed for Cosmos dbt ls at DAG parse time)
ENV SNOWFLAKE_USER="ipgross"
ENV SNOWFLAKE_PRIVATE_KEY_PATH="/usr/local/airflow/rsa_key.p8"
ENV STUDENT_SCHEMA="ipgross"
ENV SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="Houston25"

# USER root
# COPY ./dbt_project ./dbt_project
# COPY --chown=astro:0 . .

# install dbt into a virtual environment
RUN python -m venv dbt_venv && source dbt_venv/bin/activate && \
    pip install --no-cache-dir -r dbt_project/dbt-requirements.txt  && \
    cd dbt_project && dbt deps && cd .. && \
    deactivate
