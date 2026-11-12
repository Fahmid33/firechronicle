# FireChronicle — Executive Model Validation Summary

**To:** Team Lead & Technical Steering Committee
**From:** Member 2 (Data Scientist)
**Date:** November 12, 2026
**Document Purpose:** Executive sign-off summary for multi-year empirical model selection (Model 0 vs Model 1) across the 2012–2020 NASA FIRMS Pará calibration dataset.

---

## 1. Executive Recommendation: Provisional Promotion of Model 1 (Negative Binomial NB2)

Based on rigorous, leak-free empirical evaluation across 9 years of NASA FIRMS observations ($122,688$ full-panel records; $23,010$ clean paired-positive records), **Model 1 (Negative Binomial NB2 count regression)** demonstrates overwhelming statistical superiority over the Model 0 Ratio-of-Totals baseline:

- **Temporal Out-of-Time Generalization (Train: 2012–2018, Test: 2019–2020)**:
  - **21.2% Reduction in Mean Absolute Error (MAE)**: $35.44$ vs $44.99$.
  - **54.8% Reduction in Mean Poisson Deviance**: $25.01$ vs $55.31$.
  - **Controlled Aggregate Bias**: $-11.50\%$ (vs $-12.91\%$).
- **Spatial Cross-Validation (80% Train Blocks, 20% Held-Out Unseen Blocks)**:
  - **33.6% Reduction in MAE**: $35.79$ vs $53.87$.
  - **62.8% Reduction in Mean Poisson Deviance**: $20.95$ vs $56.35$.
  - **Low Aggregate Bias**: $+4.55\%$ (vs $-4.38\%$).
- **Diurnal Realism**: Parameterizes the $+1.2618$ coefficient ($\approx 3.53\times$ boost) for nighttime passes, reflecting VIIRS's superior sensitivity without daytime solar reflection noise.
- **Overdispersion Stability**: The latent overdispersion parameter $\alpha \approx 0.33$ is stable and well-behaved across all 9 years when seasonal fixed effects are included.

---

## 2. Reconciled Calibration Baseline & Truncation Invariants

1. **January 2012 Exclusion Rule**: S-NPP VIIRS observations begin on January 20, 2012. Days 1–19 are missing, causing an artificial monthly ratio artifact ($k = 0.82$). January 2012 is **strictly excluded** from all monthly calibration and evaluation sets.
2. **Mutually Exclusive Subpopulation Accounting (Clean 2012–2020, Post-Exclusion)**:
   - Clean Full-Panel Total: **121,552 records**
     - Both Sensors Missing (`M = <NA>, V = <NA>`): **78,961 records**
     - Active Sparse Detections Total: **42,591 records**
       - **Paired-Positive (`M > 0, V > 0`)**: **23,010 records** ($54.03\%$) — *Primary Validation Population*
       - **VIIRS-Only (`M = <NA>, V > 0`)**: **18,747 records** ($44.02\%$) — *Small/unobserved MODIS fires*
       - **MODIS-Only (`M > 0, V = <NA>`)**: **834 records** ($1.96\%$)
3. **Sensor-Version Attribution & Group Totals**:
   - 2012–2017 (Aqua MODIS Collection 6.2, S-NPP VIIRS Collection 2): **246,400 MODIS** / **1,529,900 VIIRS** ($k = 6.209010$).
   - 2018–2020 (Aqua MODIS Collection 6.03, S-NPP VIIRS Collection 2): **97,671 MODIS** / **666,631 VIIRS** ($k = 6.825271$).
   - Total 9-Year Sum: **344,071 MODIS** / **2,196,531 VIIRS** ($k = 6.383947$).
   - Labels are preserved exactly as delivered; version equivalence is not assumed without official NASA documentation.

---

## 3. Clarification on Sensitivity Analysis, Landscape Scope & Physical Attribution

- **Zero-Imputation Sensitivity**: In blocks where VIIRS detected fires but MODIS was unobserved ($N = 4,168$ records in 2019–2020, observed VIIRS $= 28,486$, average observed $= 6.83$ detections/record):
  - **Model 0 (Ratio Baseline)**: Predicts $\widehat{V} = 0.0$ for all records (average predicted $= 0.00$), yielding **exact $-100.00\%$ aggregate bias** and severe Poisson deviance ($306.21$).
  - **Model 1 (Negative Binomial)**: Predicts non-zero baseline conditioned on month and diurnal pass. Predicted sum $= 29,964.01$ (average predicted $= \mathbf{7.19}$ detections/record vs observed average of $6.83$), producing **$+5.19\%$ aggregate bias** and controlled deviance ($8.60$).
- **Experimental Status Disclaimer**: Missing-to-zero conversions are strictly **exploratory experimental assumptions** evaluated solely for sensitivity analysis. They do **not** represent validated satellite coverage or clear-sky ground observation proof. Unobserved cells remain `<NA>` in data stores and will **not** be automatically converted to 0 in production without independent cloud-mask verification.
- **Landscape Scope Invariant**: The provisional recommendation of Model 1 applies strictly to the **observed paired-positive detection subpopulation** ($M > 0$ and $V > 0$). It does **not** imply scientifically validated estimates across the entire landscape (which includes $78,961$ full-panel unobserved/cloud-covered records).
- **Physical Attribution**: Missing MODIS detections do not solely prove sensor resolution limits ($1\text{ km}$ vs $375\text{ m}$); they reflect the joint influence of minimum detectable fire radiative power, scan-angle distortion, ephemeral tropical cloud obscuration, and overpass timing differences.

---

## 4. Current Blockers & Next Actions

| Component | Status | Required Action |
| :--- | :--- | :--- |
| **Model Selection** | **PROVISIONALLY APPROVED** | Negative Binomial (NB2) selected as primary candidate. |
| **Test Suite** | **100% GREEN (94/94 PASSING)** | Automated unit and contract tests verified. |
| **Backend Demo Package** | **UNTOUCHED / SHA-256 VERIFIED** | `model/backend_integration_demo/` preserved byte-for-byte. |
| **Historical Data (2002–2011)** | **MISSING UPSTREAM** | Awaiting Member 1 (Data Engineer) delivery of real pre-2012 MODIS 50 km block Parquet tables. |
| **Production Model Artifact** | **HELD (No unnecessary overwrite)** | Production `model.joblib` and historical 14-column Parquet will be trained and exported once pre-2012 data arrives. |
