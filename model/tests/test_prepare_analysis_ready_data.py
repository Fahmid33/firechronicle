"""Unit tests for prepare_analysis_ready_data.py.

Tests verify:
- Verification of 2019 source files, manifest, master table, and coverage companion
- Conversion of eligible outer-join NULL counterparts (absent FIRMS positive records) to integer 0
- Exact row count preservation (4,638)
- Exact preservation of positive detection counts and totals (MODIS: 33,705; VIIRS: 215,918)
- Rejection of invalid schemas, negative counts, duplicate composite keys, and altered positives
- Preservation of coverage_status = 'unknown'
- Full audit report structure and invariants
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from prepare_analysis_ready_data import (
    EXPECTED_COLUMNS,
    EXPECTED_TOTAL_ROWS,
    EXPECTED_MODIS_SUM,
    EXPECTED_VIIRS_SUM,
    EXPECTED_MODIS_NULLS,
    EXPECTED_VIIRS_NULLS,
    load_and_verify_sources,
    resolve_year_dataset_paths,
    transform_to_analysis_ready,
    build_full_audit_document,
    save_analysis_ready_dataset,
)


@pytest.fixture
def mock_overlap_df():
    """Create a minimal synthetic DataFrame with nullable counts matching 10-column schema."""
    return pd.DataFrame({
        "region_id": ["BR-PA", "BR-PA", "BR-PA", "BR-PA"],
        "block_id": ["120_-50", "120_-51", "121_-50", "121_-51"],
        "block_ix": [120, 120, 121, 121],
        "block_iy": [-50, -51, -50, -51],
        "year": [2019, 2019, 2019, 2019],
        "month": [8, 8, 8, 8],
        "daynight": ["D", "D", "N", "N"],
        "modis_count": pd.Series([10, pd.NA, 25, pd.NA], dtype="Int64"),
        "viirs_count": pd.Series([50, 20, pd.NA, 100], dtype="Int64"),
        "coverage_status": ["unknown", "unknown", "unknown", "unknown"],
    })


def test_transform_to_analysis_ready_mock(mock_overlap_df):
    """Test that eligible nulls are converted to 0 while positive values are preserved."""
    df_out, audit = transform_to_analysis_ready(mock_overlap_df)

    assert len(df_out) == 4
    assert df_out["modis_count"].isna().sum() == 0
    assert df_out["viirs_count"].isna().sum() == 0

    # Check converted values
    assert df_out.loc[1, "modis_count"] == 0
    assert df_out.loc[3, "modis_count"] == 0
    assert df_out.loc[2, "viirs_count"] == 0

    # Check preserved positive values
    assert df_out.loc[0, "modis_count"] == 10
    assert df_out.loc[2, "modis_count"] == 25
    assert df_out.loc[0, "viirs_count"] == 50
    assert df_out.loc[1, "viirs_count"] == 20
    assert df_out.loc[3, "viirs_count"] == 100

    # Check sums
    assert df_out["modis_count"].sum() == 35
    assert df_out["viirs_count"].sum() == 170

    # Check audit counts
    assert audit["modis_nulls_converted_to_zero"] == 2
    assert audit["viirs_nulls_converted_to_zero"] == 1
    assert audit["both_positive_records_unaltered"] == 1


def test_transform_rejects_negative_counts(mock_overlap_df):
    """Negative counts must raise ValueError."""
    bad_df = mock_overlap_df.copy()
    bad_df.loc[0, "modis_count"] = -5
    with pytest.raises(ValueError, match="negative MODIS counts"):
        transform_to_analysis_ready(bad_df)


def test_transform_rejects_duplicate_composite_keys(mock_overlap_df):
    """Duplicate block-year-month-daynight keys must raise ValueError."""
    dup_df = pd.concat([mock_overlap_df, mock_overlap_df.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate composite keys"):
        transform_to_analysis_ready(dup_df)


def test_transform_rejects_non_unknown_coverage(mock_overlap_df):
    """Coverage status other than 'unknown' must raise ValueError."""
    bad_df = mock_overlap_df.copy()
    bad_df.loc[0, "coverage_status"] = "complete"
    with pytest.raises(ValueError, match="Coverage status must remain 'unknown'"):
        transform_to_analysis_ready(bad_df)


def test_resolve_year_dataset_paths():
    """Verify reusable year path resolution for 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020 and future year folders."""
    for year in (2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020):
        paths = resolve_year_dataset_paths(year)
        assert paths["overlap"].name == f"overlap_training_{year}.parquet"
        assert paths["overlap"].exists()
        assert paths["master"].name == f"firechronicle_master_{year}.parquet"
        assert paths["master"].exists()
        assert paths["coverage"].name == f"coverage_para_{year}.parquet"
        assert paths["coverage"].exists()
        assert paths["manifest"].name == f"audit_{year}.json"
        assert paths["manifest"].exists()


def test_load_and_verify_sources_real_files():
    """Verify loading real 2019 dataset against master, coverage, and manifest."""
    real_dir = Path("model/data/real/2019")
    if not real_dir.exists():
        real_dir = Path("model/data/real")
    if not (real_dir / "overlap_training_2019.parquet").exists():
        pytest.skip("Real 2019 Pará data not present.")

    cov_file = real_dir / "coverage_para_2019.parquet" if (real_dir / "coverage_para_2019.parquet").exists() else real_dir / "coverage_para.parquet"
    man_file = real_dir / "audit_2019.json" if (real_dir / "audit_2019.json").exists() else real_dir / "manifest.json"

    df_raw, verif = load_and_verify_sources(
        overlap_path=real_dir / "overlap_training_2019.parquet",
        master_path=real_dir / "firechronicle_master_2019.parquet",
        coverage_path=cov_file,
        manifest_path=man_file,
    )

    assert len(df_raw) == EXPECTED_TOTAL_ROWS
    assert verif["checks_passed"] is True
    assert verif["details"]["initial_modis_nulls"] == EXPECTED_MODIS_NULLS
    assert verif["details"]["initial_viirs_nulls"] == EXPECTED_VIIRS_NULLS
    assert verif["details"]["initial_modis_sum"] == EXPECTED_MODIS_SUM
    assert verif["details"]["initial_viirs_sum"] == EXPECTED_VIIRS_SUM
    assert verif.get("master_verified") is True
    assert verif.get("coverage_evidence_verified") is True


def test_end_to_end_real_2019_transformation(tmp_path):
    """Run full transformation on real 2019 data and verify output parquet and audit report."""
    real_dir = Path("model/data/real/2019")
    if not real_dir.exists():
        real_dir = Path("model/data/real")
    if not (real_dir / "overlap_training_2019.parquet").exists():
        pytest.skip("Real 2019 Pará data not present.")

    cov_file = real_dir / "coverage_para_2019.parquet" if (real_dir / "coverage_para_2019.parquet").exists() else real_dir / "coverage_para.parquet"
    man_file = real_dir / "audit_2019.json" if (real_dir / "audit_2019.json").exists() else real_dir / "manifest.json"

    df_raw, verif = load_and_verify_sources(
        overlap_path=real_dir / "overlap_training_2019.parquet",
        master_path=real_dir / "firechronicle_master_2019.parquet",
        coverage_path=cov_file,
        manifest_path=man_file,
    )

    df_out, audit = transform_to_analysis_ready(df_raw, source_verification=verif)
    audit_doc = build_full_audit_document(audit, manifest_data=verif.get("manifest"))

    out_parquet = tmp_path / "overlap_training_2019_analysis_ready.parquet"
    out_audit = tmp_path / "overlap_training_2019_analysis_ready_audit.json"

    save_analysis_ready_dataset(df_out, out_parquet, audit_doc, out_audit)

    # Read back and verify Parquet
    df_read = pd.read_parquet(out_parquet)
    assert len(df_read) == 4638
    assert list(df_read.columns) == EXPECTED_COLUMNS
    assert df_read["modis_count"].isna().sum() == 0
    assert df_read["viirs_count"].isna().sum() == 0
    assert df_read["modis_count"].sum() == 33705
    assert df_read["viirs_count"].sum() == 215918
    assert (df_read["coverage_status"] == "unknown").all()

    # Read back and verify JSON audit
    with open(out_audit, "r", encoding="utf-8") as f:
        audit_read = json.load(f)

    tm = audit_read["transformation_metrics"]
    assert tm["total_records"] == 4638
    assert tm["modis_nulls_converted"] == 2036
    assert tm["viirs_nulls_converted"] == 118
    assert tm["both_positive_records"] == 2484
    assert tm["total_modis_detections"] == 33705
    assert tm["total_viirs_detections"] == 215918
    assert tm["zero_distribution"]["modis_zero_viirs_positive_count"] == 2036
    assert tm["zero_distribution"]["modis_positive_viirs_zero_count"] == 118
    assert tm["zero_distribution"]["both_zero_count"] == 0
    assert all(audit_read["invariants_verified"].values())
