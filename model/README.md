# FireChronicle - Data Science & Model Workspace

Welcome to the **FireChronicle** Data Science environment!

As **Member 2 (Data Scientist)**, your mission is to harmonize **Aqua MODIS** hotspot detection counts into **Suomi NPP VIIRS-equivalent** counts for the region of **Pará, Brazil** (`region_id = BR-PA`).

---

## 📁 Directory Structure & Team Handoff Deliverables

```text
model/
├── .venv/                              # Isolated Python virtual environment (ignored by Git)
├── artifacts/                          # Versioned model weights and calibration parameters
│   └── ratio_model.joblib
├── backend_integration_demo/           # Synthetic handoff package for Backend smoke testing
│   ├── estimated_viirs_block_month.parquet # 14-column precomputed synthetic estimates
│   ├── model_info.json                 # Synthetic model metadata and disclaimers
│   └── validation_metrics.json         # Synthetic baseline metrics fixture
├── data/
│   ├── processed/                      # Analysis-ready derived datasets (outer-join reconciled)
│   │   ├── overlap_training_2019_analysis_ready.parquet
│   │   └── overlap_training_2019_analysis_ready_audit.json
│   ├── real/                           # Real satellite observations (from Data Engineer)
│   │   ├── 2012/                       # Delivered finalized 2012 package (10 files)
│   │   ├── 2013/                       # Delivered finalized 2013 package (10 files)
│   │   ├── 2014/                       # Delivered finalized 2014 package (10 files)
│   │   ├── 2015/                       # Delivered finalized 2015 package (10 files)
│   │   ├── 2016/                       # Delivered finalized 2016 package (10 files)
│   │   ├── 2017/                       # Delivered finalized 2017 package (10 files)
│   │   ├── 2018/                       # Delivered finalized 2018 package (10 files)
│   │   ├── 2019/                       # Delivered finalized 2019 package (10 files)
│   │   ├── 2020/                       # Delivered finalized 2020 package (10 files)
│   │   └── dataset_inventory.json      # Multi-year intake registry and audit catalog
│   └── synthetic/                      # Synthetic/mock datasets for rapid offline prototyping
│       ├── README.md
│       ├── synthetic_overlap_BR-PA.csv
│       ├── synthetic_nb_training_BR-PA.csv
│       └── synthetic_eval_multiblock_BR-PA.csv
├── tests/                              # Automated pytest suite (94 passing tests)
│   ├── test_environment.py            # Environment imports smoke test
│   ├── test_ratio_baseline.py         # Mathematical and data validation unit tests
│   ├── test_predict.py                # Backend B handoff schema and status contract tests
│   ├── test_negative_binomial.py      # Model 1 Negative Binomial unit tests
│   ├── test_validation_pipeline.py    # Holdout splitting and evaluation metric tests
│   ├── test_check_input_data.py       # Real-data intake validation and audit tests
│   └── test_prepare_analysis_ready_data.py # 2019 derivation and invariant verification tests
├── check_input_data.py                 # Real-data intake checker (CLI & module)
├── prepare_analysis_ready_data.py      # Prepares 2019 analysis-ready dataset (CLI & module)
├── model.joblib                        # Serialized baseline model artifact (for Backend B)
├── predict.py                          # Canonical Python inference interface (predict_viirs_equivalent)
├── model_info.json                     # Metadata: versions, targets, features, limitations
├── validation_metrics.json             # Held-out evaluation metrics for baseline
├── demo_model_comparison.json          # Synthetic demo evaluation report (temporal & geographic)
├── example_input.json                  # Sample input fixture for Backend B /api/v1/harmonized
├── example_output.json                 # Sample output fixture matching Rulebook schema
├── estimated_viirs_block_month.parquet # Precomputed historical estimates table
├── model-card.md                       # Comprehensive model card & scientific documentation
├── ratio_baseline.py                   # Core mathematical functions (fit_ratio, predict_ratio)
├── negative_binomial.py                # Model 1: Negative Binomial count regression
├── validation_pipeline.py              # Dual-strategy (temporal & geographic) evaluation pipeline
├── run_pipeline_demo.py                # Pipeline demo runner
├── demo_ratio.py                       # Ratio baseline demo script
├── demo_negative_binomial.py           # Negative Binomial demo script
├── requirements.txt                    # Python package dependencies
└── README.md                           # Workspace documentation and instructions
```

---

## 🔬 Scientific Scope & Pipeline Boundary

1. **Target Region**: Pará, Brazil (`region_id = BR-PA`) exclusively.
2. **Upstream Contract (Member 1 — Data Engineer)**:
   - Downloads FIRMS Brazil country-year archives.
   - Filters to official Pará IBGE administrative boundary.
   - Filters to `satellite == "Aqua"` (MODIS) and `satellite == "N"` (VIIRS S-NPP).
   - Projects coordinates to **EPSG:6933** and derives 50 km block IDs (`"bx_by"`).
   - Aggregates detection counts by `block_id`, `year`, `month`, `daynight`.
3. **Model Input**: The Data Scientist model does **not** ingest raw FIRMS point CSVs directly; it consumes pre-aggregated 50 km block tables.
4. **Coverage Principle**: Missing observation groups in FIRMS tables are **not** assumed to be zero fires; they are marked `coverage_status = "unknown"` (coverage-unadjusted).
5. **Zero-MODIS Limitation**: Model 0 (Ratio-of-Totals) strictly yields $\widehat{V} = 0.0$ when $M = 0$. Because VIIRS (375 m resolution) detects small fires that MODIS (1 km) misses, this is a mathematical property, **not** proof of a fire-free observation. Model 1 (Negative Binomial) estimates positive counts at $M = 0$ due to the log-link intercept, but this does not prove physical fire recovery.

---

## 🚀 Running the Code on Windows

### 1. Run the Complete Test Suite (94 Tests)
```powershell
pytest tests -v
```

### 2. Audit Incoming Datasets with the Real-Data Intake Checker
When Member 1 delivers the empirical overlap dataset (e.g. `overlap_training.parquet` or `.csv`), audit it before running any model fitting:

```powershell
# Basic intake check
python check_input_data.py data/real/overlap_training.parquet

# With configured train/test years and blocks
python check_input_data.py data/real/overlap_training.parquet `
    --train-years 2012 2013 2014 2015 2016 2017 2018 2019 `
    --test-years 2020 `
    --train-blocks 120_-50 121_-50 `
    --test-blocks 122_-50
```

> [!IMPORTANT]
> **Scientific Caveat on Intake Validation:**
> A `PASS (SCHEMA & STRUCTURAL CHECKS PASSED)` status confirms only that the table schema, column data types, key uniqueness, and canonical ID formatting comply with the Data Engineer contract.
> The intake checker **cannot prove** that Member 1 correctly clipped the points to the official IBGE Pará boundary or strictly filtered sensors to Aqua MODIS (`satellite == "Aqua"`) and Suomi NPP VIIRS (`satellite == "N"`) merely from `region_id == "BR-PA"` and `block_id` regex matching. Upstream geographic clipping and sensor provenance must be verified through Member 1's preprocessing pipeline. Furthermore, `coverage_status == "unknown"` records remain unverified for observation coverage (clear-sky vs cloud/unobserved), and rows with MODIS=0, VIIRS>0 reflect sensor detection-count mismatches rather than confirmed physical fires or proven subpixel detections.

### 3. Run Candidate Demos
```powershell
# Model 0 Ratio-of-Totals baseline demo
python demo_ratio.py

# Model 1 Negative Binomial regression demo
python demo_negative_binomial.py

# Dual-strategy (temporal & geographic) holdout pipeline demo
python run_pipeline_demo.py
```
