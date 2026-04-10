"""
Infraestrutura temporal do SolveLicita no BigQuery.

Cria tabelas historicas, tabelas placeholder da camada de ML e views
analiticas de acesso rapido.
"""

from __future__ import annotations

import logging

from .bigquery_loader import (
    get_bigquery_client,
    get_bigquery_project,
    is_bigquery_enabled,
)

logger = logging.getLogger(__name__)

DATASET_SNAPSHOTS = "snapshots"
DATASET_ML = "ml"
DATASET_ANALYTICS = "analytics"


def _ddl_statements(project: str) -> list[str]:
    return [
        f"CREATE SCHEMA IF NOT EXISTS `{project}.{DATASET_SNAPSHOTS}`",
        f"CREATE SCHEMA IF NOT EXISTS `{project}.{DATASET_ML}`",
        f"CREATE SCHEMA IF NOT EXISTS `{project}.{DATASET_ANALYTICS}`",
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.snapshots.snapshot_runs` (
          snapshot_run_id STRING NOT NULL,
          snapshot_date DATE NOT NULL,
          snapshot_ts TIMESTAMP NOT NULL,
          uf STRING NOT NULL,
          run_type STRING NOT NULL,
          pipeline_mode STRING,
          source_mode STRING,
          methodology_version STRING NOT NULL,
          pipeline_version STRING,
          status STRING NOT NULL,
          rows_written INT64,
          rows_scored INT64,
          rows_sem_dados INT64,
          score_avg FLOAT64,
          score_median FLOAT64,
          score_min FLOAT64,
          score_max FLOAT64,
          source_siconfi_ref STRING,
          source_dca_ref STRING,
          source_cauc_ref STRING,
          source_pncp_ref STRING,
          notes STRING,
          created_at TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, status
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.snapshots.municipios_risco_snapshot` (
          snapshot_run_id STRING NOT NULL,
          snapshot_date DATE NOT NULL,
          snapshot_ts TIMESTAMP NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          ente STRING,
          populacao INT64,
          methodology_version STRING NOT NULL,

          score FLOAT64,
          classificacao STRING,
          score_base FLOAT64,
          score_bruto FLOAT64,

          anos_entregues INT64,
          n_anos_cronicos INT64,
          rproc_pct_atual FLOAT64,
          lliq_raw FLOAT64,
          eorcam_raw FLOAT64,
          qsiconfi FLOAT64,
          ccauc FLOAT64,
          autonomia_media FLOAT64,

          eorcam_norm FLOAT64,
          lliq_norm FLOAT64,
          rproc_norm FLOAT64,
          autonomia_norm FLOAT64,

          contrib_eorcam FLOAT64,
          contrib_lliq FLOAT64,
          contrib_qsiconfi FLOAT64,
          contrib_ccauc FLOAT64,
          contrib_autonomia FLOAT64,
          contrib_rproc FLOAT64,

          pen_lliq_parcial FLOAT64,
          pen_situacional FLOAT64,

          dias_atraso INT64,
          decay_fator FLOAT64,
          dado_suspeito BOOL,
          dado_suspeito_lliq BOOL,
          dado_defasado BOOL,
          lliq_parcial BOOL,
          autonomia_critica BOOL,

          n_graves INT64,
          n_moderadas INT64,
          n_leves INT64,
          pendencias STRING,
          pendencias_cauc_json STRING,

          n_licitacoes INT64,
          valor_homologado_total FLOAT64,
          n_dispensa INT64,
          valor_hom_dispensa FLOAT64,
          pct_dispensa FLOAT64,
          ano_ultima_licitacao INT64,
          alerta_dispensa BOOL
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, cod_ibge
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.feature_base_temporal` (
          snapshot_date DATE NOT NULL,
          snapshot_run_id STRING NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          methodology_version STRING,
          feature_version STRING,
          score FLOAT64,
          classificacao STRING,
          lliq_raw FLOAT64,
          eorcam_raw FLOAT64,
          rproc_pct_atual FLOAT64,
          qsiconfi FLOAT64,
          ccauc FLOAT64,
          autonomia_media FLOAT64,
          n_anos_cronicos INT64,
          anos_entregues INT64,
          has_pncp BOOL,
          has_cauc BOOL,
          has_dca BOOL,
          has_siconfi BOOL,
          is_modeling_ready BOOL,
          created_at TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, cod_ibge
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.feature_enriched_temporal` (
          snapshot_date DATE NOT NULL,
          snapshot_run_id STRING NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          feature_version STRING NOT NULL,
          features_json STRING,
          created_at TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, cod_ibge
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.labels_municipios` (
          snapshot_date DATE NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          label_version STRING,
          label_evento_12m BOOL,
          label_evento_6m BOOL,
          target_rproc_12m FLOAT64,
          target_rproc_6m FLOAT64,
          label_deterioracao_classe_12m BOOL,
          created_at TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, cod_ibge
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.training_dataset` (
          snapshot_date DATE NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          feature_version STRING,
          label_version STRING,
          training_cut STRING,
          train_eligible BOOL,
          payload_json STRING,
          created_at TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY uf, cod_ibge
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.model_registry` (
          model_version STRING NOT NULL,
          created_at TIMESTAMP,
          task_type STRING,
          label_name STRING,
          feature_version STRING,
          train_start_date DATE,
          train_end_date DATE,
          valid_start_date DATE,
          valid_end_date DATE,
          algorithm STRING,
          hyperparams_json STRING,
          metrics_json STRING,
          artifact_uri STRING,
          status STRING,
          notes STRING
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{project}.ml.predictions_municipios` (
          snapshot_date DATE NOT NULL,
          uf STRING NOT NULL,
          cod_ibge STRING NOT NULL,
          model_version STRING NOT NULL,
          prob_evento_12m FLOAT64,
          score_ml FLOAT64,
          alerta_precoce_ml BOOL,
          top_fatores_ml_json STRING,
          prediction_ts TIMESTAMP
        )
        PARTITION BY snapshot_date
        CLUSTER BY model_version, uf, cod_ibge
        """,
        f"""
        CREATE OR REPLACE VIEW `{project}.analytics.vw_municipios_risco_latest` AS
        SELECT *
        FROM `{project}.snapshots.municipios_risco_snapshot`
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY uf, cod_ibge
          ORDER BY snapshot_ts DESC, snapshot_run_id DESC
        ) = 1
        """,
        f"""
        CREATE OR REPLACE VIEW `{project}.analytics.vw_municipios_risco_trajetoria` AS
        SELECT
          snapshot_run_id,
          snapshot_date,
          snapshot_ts,
          uf,
          cod_ibge,
          ente,
          score,
          classificacao,
          score_base,
          score_bruto,
          lliq_raw,
          eorcam_raw,
          rproc_pct_atual,
          qsiconfi,
          ccauc,
          autonomia_media,
          n_anos_cronicos,
          anos_entregues,
          n_graves,
          n_moderadas,
          n_leves,
          dado_defasado,
          autonomia_critica,
          alerta_dispensa
        FROM `{project}.snapshots.municipios_risco_snapshot`
        """,
        f"""
        CREATE OR REPLACE VIEW `{project}.analytics.vw_municipios_risco_diff_last_run` AS
        WITH ranked AS (
          SELECT
            *,
            ROW_NUMBER() OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS rn,
            LEAD(snapshot_run_id) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS snapshot_run_id_anterior,
            LEAD(snapshot_date) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS snapshot_date_anterior,
            LEAD(score) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS score_anterior,
            LEAD(classificacao) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS classificacao_anterior,
            LEAD(n_graves) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS n_graves_anterior,
            LEAD(ccauc) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts DESC, snapshot_run_id DESC
            ) AS ccauc_anterior
          FROM `{project}.snapshots.municipios_risco_snapshot`
        )
        SELECT
          snapshot_run_id,
          snapshot_date,
          uf,
          cod_ibge,
          ente,
          score AS score_atual,
          score_anterior,
          score - score_anterior AS delta_score,
          classificacao AS classificacao_atual,
          classificacao_anterior,
          classificacao != classificacao_anterior AS mudou_classificacao,
          n_graves AS n_graves_atual,
          n_graves_anterior,
          ccauc AS ccauc_atual,
          ccauc_anterior
        FROM ranked
        WHERE rn = 1
        """,
        f"""
        CREATE OR REPLACE VIEW `{project}.analytics.vw_cauc_persistencia` AS
        WITH base AS (
          SELECT
            snapshot_run_id,
            snapshot_date,
            snapshot_ts,
            uf,
            cod_ibge,
            ente,
            n_graves,
            n_moderadas,
            n_leves,
            ccauc,
            CASE WHEN COALESCE(n_graves, 0) > 0 THEN 1 ELSE 0 END AS has_grave
          FROM `{project}.snapshots.municipios_risco_snapshot`
        ),
        calc AS (
          SELECT
            *,
            COUNT(*) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts
              ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
            ) AS janela_6_execucoes,
            COUNT(*) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts
              ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            ) AS janela_12_execucoes,
            SUM(has_grave) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts
              ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
            ) AS n_execucoes_com_grave_ultimas_6,
            SUM(has_grave) OVER (
              PARTITION BY uf, cod_ibge
              ORDER BY snapshot_ts
              ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
            ) AS n_execucoes_com_grave_ultimas_12
          FROM base
        )
        SELECT
          snapshot_run_id,
          snapshot_date,
          uf,
          cod_ibge,
          ente,
          n_graves,
          n_moderadas,
          n_leves,
          ccauc,
          CAST(has_grave AS BOOL) AS has_grave,
          n_execucoes_com_grave_ultimas_6,
          n_execucoes_com_grave_ultimas_12,
          CASE
            WHEN janela_6_execucoes = 6 AND n_execucoes_com_grave_ultimas_6 = 6
            THEN TRUE ELSE FALSE
          END AS bloqueio_grave_persistente_6_execucoes,
          CASE
            WHEN janela_12_execucoes = 12 AND n_execucoes_com_grave_ultimas_12 = 12
            THEN TRUE ELSE FALSE
          END AS bloqueio_grave_persistente_12_execucoes
        FROM calc
        """,
    ]


def ensure_temporal_infra() -> bool:
    if not is_bigquery_enabled():
        logger.warning(
            "BigQuery nao esta habilitado; infraestrutura temporal nao foi criada."
        )
        return False

    client = get_bigquery_client()
    project = get_bigquery_project()

    for ddl in _ddl_statements(project):
        client.query(ddl).result()

    logger.info(
        "Infraestrutura temporal garantida em %s.{snapshots,ml,analytics}",
        project,
    )
    return True


if __name__ == "__main__":
    ok = ensure_temporal_infra()
    print("Infraestrutura temporal pronta." if ok else "Infraestrutura temporal nao criada.")
