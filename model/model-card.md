# FireChronicle Model Card — Ratio-of-Totals Baseline

> [!WARNING]
> **DEMO / SYNTHETIC / NOT SCIENTIFICALLY VALIDATED**
> All models, parameters, validation metrics, and historical estimates in this directory are calibrated on **synthetic mock fixtures** for software pipeline testing and integration. They do **not** represent real NASA Pará observations and must **not** be used for scientific conclusions or operational wildfire reporting.

---

## Model Overview
- **Model Name**: Ratio-of-Totals Baseline (`Model 0`)
- **Version**: `ratio-baseline-v1.0-synthetic-demo`
- **Owner**: Member 2 (Data Scientist)
- **Downstream Consumer**: Member 4 (Backend B) & Member 5 (Frontend)
- **Primary Interface**: [`model/predict.py`](file:///c:/Users/Farjad/OneDrive/Documents/FireChronicle/model/predict.py)
- **Production Ready**: **No** (Awaiting empirical Pará overlap dataset from Member 1)

---

## Intended Purpose & Scientific Scope
- **Target Geographic Domain**: State of Pará, Brazil (`region_id = BR-PA`) exclusively.
- **Reference Sensors**:
  - Input Predictor: Aqua MODIS (1 km pixel resolution).
  - Target Calibration: Suomi NPP VIIRS (375 m pixel resolution).
- **Modeling Unit**: 50 km grid block (EPSG:6933, `block_id = "bx_by"`) × year × month × day/night pass.
- **Target Metric**: Estimated VIIRS S-NPP-equivalent hotspot detection counts.
  *(Not unique fire perimeters, burned area, or fire spread forecasts).*

---

## Mathematical Formulation
$$\widehat{V} = M \times k$$
where:
$$k = \frac{\sum_{\text{train}} V}{\sum_{\text{train}} M}$$

On current synthetic calibration data (2018–2019):
$$k = 3.2000$$

---

## Known Scientific Limitations & Guardrails
1. **Zero-MODIS Non-Recovery**: When $M = 0$, $\widehat{V} = 0.0$. Because VIIRS has 375 m resolution compared to MODIS's 1 km resolution, VIIRS frequently detects small fires where MODIS records zero detections ($M=0$). The Ratio-of-Totals model cannot recover these missed detections.
2. **Coverage Evidence**: When derived strictly from FIRMS positive-detection CSVs without cloud/clear-sky proof, observations are labeled `coverage_status: unknown` (coverage-unadjusted).
3. **Pará Boundary Filtering**: The model applies only to records strictly inside Pará's official IBGE administrative boundary.
4. **Validation Scope**: Current metrics in `validation_metrics.json` reflect a single joint holdout slice on synthetic mock records (year 2020, block `121_-51`, $N=6$). They do **not** claim separate orthogonal temporal and spatial cross-validation experiments.

---

## Response Status Definitions (Rulebook Section 5, p. 6)
- `ok_preliminary`: Valid prediction completed.
- `unsupported_region`: Request is outside Pará (`region_id != "BR-PA"`). Result is strictly `null`.
- `unsupported_period`: Date is outside supported Aqua MODIS science record (prior to July 2002). Result is strictly `null`.
- `out_of_training_range`: Year is beyond calibration/operational scope (> 2026). Result is strictly `null`.
- `insufficient_coverage`: Usable satellite coverage is flagged as insufficient. Result is strictly `null`.
- `missing_required_feature`: Missing required count, time feature, or canonical `bx_by` block ID. Result is strictly `null`.
- `model_error`: Numerical or data type error during evaluation. Result is strictly `null`.

*Backend B must preserve `null` and exact status; never substitute zero.*
