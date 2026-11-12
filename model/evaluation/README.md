# FireChronicle — Multi-Year Evaluation & Consistency Audit Suite

This directory contains the independent reproducibility scripts, leakage verifications, and empirical benchmark results for the **2012–2020 NASA FIRMS multi-year calibration collection** for Pará, Brazil (`region_id = BR-PA`).

---

## Files

1. **`multiyear_eval_results.json`**:
   The authoritative, leak-free evaluation results artifact storing performance metrics across Strategy A (Temporal Holdout: 2019–2020), Strategy B (Geographic Holdout: 94 unseen blocks), and the zero-imputation sensitivity experiment.

2. **`verify_reproducibility.py`**:
   Verifies:
   - Zero leakage between training and testing splits (temporal years and spatial blocks).
   - Strict adherence to the primary evaluation population (**paired-positive satellite detections only**).
   - Exact numerical reproduction of MAE, Poisson deviance, and aggregate bias for Model 0 and Model 1.

3. **`audit_consistency.py`**:
   Verifies:
   - 9-year full-panel ($122,688$ rows) and sparse active detection row counts.
   - Mutually exclusive subpopulation partitioning before and after January 2012 exclusion.
   - Exact sensor version totals (Collection 6.2 vs Collection 6.03).
   - Sensitivity experiment de-biasing isolating zero-MODIS observations ($M = 0$) from pooled data.

---

## How to Run

From the project root or inside `model/`:

```powershell
# Run reproducibility and leakage verification
python model/evaluation/verify_reproducibility.py

# Run population and sensitivity consistency audit
python model/evaluation/audit_consistency.py
```
