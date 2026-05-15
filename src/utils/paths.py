from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.settings import PROJECT_ROOT

LEGACY_DEFAULT_UF = "PB"

ROLE_CANONICAL = "canonical"
ROLE_AUDIT = "audit_export"
ROLE_CHECKPOINT = "checkpoint"
ROLE_COMPAT = "legacy_compat"


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    data: Path
    raw: Path
    processed: Path
    outputs: Path
    app_data: Path


@dataclass(frozen=True)
class UfPaths:
    uf: str
    workspace: WorkspacePaths
    raw_siconfi: Path
    raw_cauc: Path
    raw_dca: Path
    raw_pncp: Path
    processed: Path
    outputs: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "raw_siconfi": self.raw_siconfi,
            "raw_cauc": self.raw_cauc,
            "raw_dca": self.raw_dca,
            "raw_pncp": self.raw_pncp,
            "processed": self.processed,
            "outputs": self.outputs,
        }


@dataclass(frozen=True)
class LocalArtifactSpec:
    key: str
    bucket: str
    filename_template: str
    role: str
    description: str

    def render_filename(self, uf: str) -> str:
        return self.filename_template.format(uf=uf.upper(), uf_lower=uf.lower())


ARTIFACT_SPECS: dict[str, LocalArtifactSpec] = {
    "municipios_tabela": LocalArtifactSpec(
        key="municipios_tabela",
        bucket="processed",
        filename_template="municipios_{uf_lower}_tabela.csv",
        role=ROLE_CANONICAL,
        description="Cadastro municipal local por UF, usado como backbone geografico.",
    ),
    "cauc_situacao": LocalArtifactSpec(
        key="cauc_situacao",
        bucket="processed",
        filename_template="cauc_situacao_{uf_lower}.csv",
        role=ROLE_CANONICAL,
        description="Situacao CAUC local consumida pelo modo CSV legado.",
    ),
    "siconfi_indicadores": LocalArtifactSpec(
        key="siconfi_indicadores",
        bucket="processed",
        filename_template="siconfi_indicadores_{uf_lower}.csv",
        role=ROLE_CANONICAL,
        description="Indicadores SICONFI locais consumidos pelo modo CSV legado.",
    ),
    "siconfi_icf": LocalArtifactSpec(
        key="siconfi_icf",
        bucket="processed",
        filename_template="siconfi_icf_{uf_lower}.csv",
        role=ROLE_AUDIT,
        description="Ranking ICF SICONFI por exercicio, usado como modulador de confianca.",
    ),
    "mart_indicadores": LocalArtifactSpec(
        key="mart_indicadores",
        bucket="processed",
        filename_template="mart_indicadores_{uf_lower}.csv",
        role=ROLE_AUDIT,
        description="Export local de auditoria do mart carregado do BigQuery.",
    ),
    "dca_indicadores": LocalArtifactSpec(
        key="dca_indicadores",
        bucket="processed",
        filename_template="dca_indicadores_{uf_lower}.csv",
        role=ROLE_AUDIT,
        description="Export local de auditoria do postprocessor de DCA.",
    ),
    "siconfi_postprocessed": LocalArtifactSpec(
        key="siconfi_postprocessed",
        bucket="processed",
        filename_template="siconfi_postprocessed_{uf_lower}.csv",
        role=ROLE_AUDIT,
        description="Export local de auditoria do postprocessor de SICONFI.",
    ),
    "score_municipios_pncp": LocalArtifactSpec(
        key="score_municipios_pncp",
        bucket="outputs",
        filename_template="score_municipios_{uf_lower}_pncp.csv",
        role=ROLE_CANONICAL,
        description="Score consolidado por municipio, artefato de saida canonico atual.",
    ),
    "score_municipios_legacy": LocalArtifactSpec(
        key="score_municipios_legacy",
        bucket="outputs",
        filename_template="score_municipios_{uf_lower}.csv",
        role=ROLE_COMPAT,
        description="Nome legado mantido apenas para compatibilidade residual.",
    ),
    "pncp_checkpoint": LocalArtifactSpec(
        key="pncp_checkpoint",
        bucket="raw_pncp",
        filename_template="pncp_parcial_{uf_lower}.jsonl",
        role=ROLE_CHECKPOINT,
        description="Checkpoint incremental local da coleta PNCP por UF.",
    ),
}

BIGQUERY_CSV_FALLBACKS: dict[str, tuple[str, ...]] = {
    "mart_indicadores_municipios": ("mart_indicadores",),
    "mart_pncp_municipios": ("score_municipios_pncp",),
    "score_municipios": ("score_municipios_legacy", "score_municipios_pncp"),
}


def get_workspace_paths(root: Path | None = None) -> WorkspacePaths:
    base_root = (root or PROJECT_ROOT).resolve()
    data_dir = base_root / "data"
    workspace = WorkspacePaths(
        root=base_root,
        data=data_dir,
        raw=data_dir / "raw",
        processed=data_dir / "processed",
        outputs=data_dir / "outputs",
        app_data=base_root / "app" / "data",
    )

    for directory in (
        workspace.data,
        workspace.raw,
        workspace.processed,
        workspace.outputs,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return workspace


def build_uf_paths(uf: str, *, root: Path | None = None, create: bool = True) -> UfPaths:
    normalized_uf = uf.upper()
    workspace = get_workspace_paths(root=root)
    uf_paths = UfPaths(
        uf=normalized_uf,
        workspace=workspace,
        raw_siconfi=workspace.raw / "siconfi" / normalized_uf,
        raw_cauc=workspace.raw / "cauc" / normalized_uf,
        raw_dca=workspace.raw / "dca" / normalized_uf,
        raw_pncp=workspace.raw / "pncp" / normalized_uf,
        processed=workspace.processed / normalized_uf,
        outputs=workspace.outputs / normalized_uf,
    )

    if create:
        for directory in uf_paths.as_dict().values():
            directory.mkdir(parents=True, exist_ok=True)

    return uf_paths


def get_paths(uf: str, *, root: Path | None = None, create: bool = True) -> dict[str, Path]:
    return build_uf_paths(uf, root=root, create=create).as_dict()


def get_artifact_spec(key: str) -> LocalArtifactSpec:
    try:
        return ARTIFACT_SPECS[key]
    except KeyError as exc:
        raise KeyError(f"Artefato local desconhecido: {key}") from exc


def get_artifact_path(
    uf: str,
    artifact_key: str,
    *,
    root: Path | None = None,
    create_parent: bool = True,
) -> Path:
    spec = get_artifact_spec(artifact_key)
    uf_paths = build_uf_paths(uf, root=root, create=create_parent)
    base_dir = getattr(uf_paths, spec.bucket)
    if create_parent:
        base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / spec.render_filename(uf_paths.uf)


def find_ufs_with_artifact(
    artifact_key: str,
    *,
    root: Path | None = None,
) -> list[str]:
    workspace = get_workspace_paths(root=root)
    spec = get_artifact_spec(artifact_key)
    base_dirs = {
        "processed": workspace.processed,
        "outputs": workspace.outputs,
        "raw_siconfi": workspace.raw / "siconfi",
        "raw_cauc": workspace.raw / "cauc",
        "raw_dca": workspace.raw / "dca",
        "raw_pncp": workspace.raw / "pncp",
    }
    base = base_dirs[spec.bucket]
    ufs = []

    if not base.exists():
        return ufs

    for item in sorted(base.iterdir()):
        if not item.is_dir():
            continue
        artifact = get_artifact_path(item.name, artifact_key, root=workspace.root, create_parent=False)
        if artifact.exists():
            ufs.append(item.name.upper())

    return ufs


def get_bigquery_csv_fallback_paths(
    table: str,
    *,
    uf: str | None = None,
    root: Path | None = None,
) -> list[Path]:
    artifact_keys = BIGQUERY_CSV_FALLBACKS.get(table, ())
    if not artifact_keys:
        return []

    target_uf = (uf or LEGACY_DEFAULT_UF).upper()
    return [
        get_artifact_path(target_uf, artifact_key, root=root, create_parent=False)
        for artifact_key in artifact_keys
    ]


# Aliases globais de compatibilidade (apontam para PB).
# Eles continuam existindo para analises e legados, mas o runtime central
# deve preferir o contrato explicito acima.
ROOT = PROJECT_ROOT
RAW = get_workspace_paths().raw
PROCESSED = build_uf_paths(LEGACY_DEFAULT_UF).processed
OUTPUTS = build_uf_paths(LEGACY_DEFAULT_UF).outputs
APP_DATA = get_workspace_paths().app_data
