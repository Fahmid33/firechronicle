"""Unit tests for the Real-Data Intake Checker (check_input_data.py).

Tests cover:
- Valid CSV and Parquet inputs
- Schema validation & missing required columns
- Non-Pará region leakage detection
- Malformed block IDs (not matching canonical EPSG:6933 'bx_by')
- block_ix / block_iy index consistency checks
- Bad types, fractional counts, negative counts
- Composite key duplicates (block_id, year, month, daynight)
- Missing counts detection without zero imputation
- Coverage status warnings and distinction from verified coverage
- Sensor-zero mismatch detection (MODIS=0, VIIRS>0)
- Configurable split leakage validation
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# Ensure model/ is in sys.path
model_dir = Path(__file__).resolve().parent.parent
if str(model_dir) not in sys.path:
    sys.path.insert(0, str(model_dir))

from check_input_data import check_overlap_dataset, load_dataset


@pytest.fixture
def sample_valid_df():
    """Create a small, canonical valid overlap DataFrame."""
    return pd.DataFrame({
        "region_id": ["BR-PA", "BR-PA", "BR-PA", "BR-PA"],
        "block_id": ["120_-50", "120_-50", "121_-50", "121_-50"],
        "block_ix": [120, 120, 121, 121],
        "block_iy": [-50, -50, -50, -50],
        "year": [2018, 2018, 2018, 2018],
        "month": [8, 8, 8, 8],
        "daynight": ["D", "N", "D", "N"],
        "modis_count": [45, 12, 0, 80],
        "viirs_count": [140, 38, 5, 260],
        "coverage_status": ["unknown", "unknown", "unknown", "unknown"]
    })


# --- 1. File Loading & Format Tests ---

def test_load_dataset_csv(tmp_path, sample_valid_df):
    """Load valid CSV file via load_dataset."""
    csv_file = tmp_path / "test.csv"
    sample_valid_df.to_csv(csv_file, index=False)

    loaded_df = load_dataset(csv_file)
    assert len(loaded_df) == 4
    audit = check_overlap_dataset(loaded_df, source_label="CSV Test")
    assert audit["is_schema_valid"] is True


def test_load_dataset_parquet(tmp_path, sample_valid_df):
    """Load valid Parquet file via load_dataset."""
    pq_file = tmp_path / "test.parquet"
    sample_valid_df.to_parquet(pq_file, index=False)

    loaded_df = load_dataset(pq_file)
    assert len(loaded_df) == 4
    audit = check_overlap_dataset(loaded_df, source_label="Parquet Test")
    assert audit["is_schema_valid"] is True


def test_load_dataset_file_not_found():
    """Raise FileNotFoundError when file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_dataset("non_existent_file.parquet")


# --- 2. Schema, Region & ID Validation Tests ---

def test_check_missing_required_column(sample_valid_df):
    """Detect missing required columns."""
    bad_df = sample_valid_df.drop(columns=["modis_count"])
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("modis_count" in err for err in audit["errors"])


def test_check_non_para_region(sample_valid_df):
    """Detect non-Pará records leaking into the table."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "region_id"] = "BR-AM"
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("Only Pará ('BR-PA') is supported" in err for err in audit["errors"])


def test_check_malformed_block_id(sample_valid_df):
    """Detect block IDs not matching canonical 'bx_by' format."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "block_id"] = "PA_BLOCK_01"
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("Malformed block IDs detected" in err for err in audit["errors"])


def test_check_block_ix_iy_consistency(sample_valid_df):
    """Verify that block_ix and block_iy match block_id when present."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "block_ix"] = 999  # Mismatch with "120_-50"
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("inconsistent with block_ix/block_iy" in err for err in audit["errors"])


def test_check_malformed_block_ix_iy_non_numeric(sample_valid_df):
    """Ensure non-numeric string values in optional block indexes do not crash the checker."""
    bad_df = sample_valid_df.copy()
    bad_df["block_ix"] = bad_df["block_ix"].astype(object)
    bad_df.loc[0, "block_ix"] = "NOT_AN_INDEX"
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("Malformed or missing values in optional block indexes" in err for err in audit["errors"])


def test_check_early_2002_aqua_horizon_detected(sample_valid_df):
    """Reject pre-July 2002 records because Aqua MODIS public science operations began July 2002."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "year"] = 2002
    bad_df.loc[0, "month"] = 3
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("Jan-Jun 2002" in err for err in audit["errors"])


def test_check_multiple_structural_errors_reported_together(sample_valid_df):
    """Checker should report multiple structural issues together rather than exiting on first error."""
    bad_df = sample_valid_df.copy()
    bad_df["modis_count"] = bad_df["modis_count"].astype(float)
    bad_df.loc[0, "region_id"] = "BR-AM"
    bad_df.loc[1, "block_id"] = "MALFORMED_BLK"
    bad_df.loc[2, "modis_count"] = -10
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("Only Pará ('BR-PA') is supported" in err for err in audit["errors"])
    assert any("Malformed block IDs detected" in err for err in audit["errors"])
    assert any("negative detection counts" in err for err in audit["errors"])


# --- 3. Types, Counts & Uniqueness Tests ---

def test_check_fractional_counts(sample_valid_df):
    """Reject fractional detection counts."""
    bad_df = sample_valid_df.copy()
    bad_df["modis_count"] = bad_df["modis_count"].astype(float)
    bad_df.loc[0, "modis_count"] = 12.5
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("fractional detection counts" in err for err in audit["errors"])


def test_check_negative_counts(sample_valid_df):
    """Reject negative detection counts."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "viirs_count"] = -5
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is False
    assert any("negative detection counts" in err for err in audit["errors"])


def test_check_duplicate_composite_keys(sample_valid_df):
    """Reject duplicate (block_id, year, month, daynight) records."""
    dup_df = pd.concat([sample_valid_df, sample_valid_df.iloc[[0]]], ignore_index=True)
    audit = check_overlap_dataset(dup_df)
    assert audit["is_schema_valid"] is False
    assert any("Duplicate records found" in err for err in audit["errors"])


def test_check_missing_values_detected(sample_valid_df):
    """Detect null count values, preserve as NULL without zero imputation, and yield PASS_WITH_WARNINGS."""
    bad_df = sample_valid_df.copy()
    bad_df.loc[0, "modis_count"] = np.nan
    audit = check_overlap_dataset(bad_df)
    assert audit["is_schema_valid"] is True
    assert audit["status"] == "PASS_WITH_WARNINGS"
    assert audit["missing_summary"].get("modis_count") == 1
    assert any("Nullable count column 'modis_count'" in w for w in audit["warnings"])


def test_check_missing_required_metadata_fails(sample_valid_df):
    """Missing required metadata/identifiers (e.g. region_id, block_id, dates) must strictly FAIL."""
    for col in ("region_id", "block_id", "year", "month", "daynight", "coverage_status"):
        bad_df = sample_valid_df.copy()
        bad_df.loc[0, col] = None
        audit = check_overlap_dataset(bad_df)
        assert audit["is_schema_valid"] is False
        assert audit["status"] == "FAIL"
        assert any(f"Required identifier/metadata column '{col}' contains" in err for err in audit["errors"])


def test_check_nullable_integer_counts_not_flagged_as_fractional(sample_valid_df):
    """Nullable integers containing <NA> must NOT be falsely flagged as fractional."""
    nullable_df = sample_valid_df.copy()
    nullable_df["modis_count"] = nullable_df["modis_count"].astype("Int64")
    nullable_df.loc[0, "modis_count"] = pd.NA
    audit = check_overlap_dataset(nullable_df)
    assert not any("fractional detection counts" in err for err in audit["errors"])


def test_check_genuine_fractional_counts_detected(sample_valid_df):
    """Genuine fractional numbers (e.g. 14.5) must be flagged as fractional errors."""
    frac_df = sample_valid_df.copy()
    frac_df["modis_count"] = frac_df["modis_count"].astype(float)
    frac_df.loc[0, "modis_count"] = 14.5
    audit = check_overlap_dataset(frac_df)
    assert audit["is_schema_valid"] is False
    assert any("fractional detection counts" in err for err in audit["errors"])


# --- 4. Coverage & Sensor-Zero Mismatch Tests ---

def test_check_sensor_zero_mismatch_analysis(sample_valid_df):
    """Verify detection of MODIS-zero/VIIRS-positive detection mismatch groups."""
    # Row 2 in sample_valid_df has modis_count=0, viirs_count=5
    audit = check_overlap_dataset(sample_valid_df)
    assert audit["is_schema_valid"] is True
    sz = audit["sensor_zero_analysis"]
    assert sz["modis_zero_viirs_positive_count"] == 1
    assert any("Sensor Detection-Count Mismatch" in warn for warn in audit["warnings"])


def test_check_coverage_status_distinction(sample_valid_df):
    """Ensure 'unknown' coverage generates a scientific caution and is not treated as complete."""
    audit = check_overlap_dataset(sample_valid_df)
    assert any("Do NOT treat 'unknown' coverage as complete" in warn for warn in audit["warnings"])


# --- 5. Split Configuration & Leakage Tests ---

def test_check_split_leakage_detected(sample_valid_df):
    """Detect overlapping years or blocks in configured holdout splits."""
    audit = check_overlap_dataset(
        sample_valid_df,
        train_years=[2018],
        test_years=[2018]  # Overlap!
    )
    assert audit["is_schema_valid"] is False
    assert any("overlapping years" in err for err in audit["errors"])
