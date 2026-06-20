FROM apache/airflow:2.9.3

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @dataform/cli@^3.0.0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
