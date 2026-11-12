# FireChronicle Final Model Card — Negative Binomial (NB2) Active Fire Harmonization

> [!IMPORTANT]
> **FINAL REPRODUCIBLE MODEL SPECIFICATION & HISTORICAL ESTIMATION PIPELINE**
> This model card documents the final, empirically calibrated **Negative Binomial (NB2) Harmonization Model** trained on the complete 2012–2020 NASA FIRMS overlap collection for Pará, Brazil, and its execution across historical Aqua MODIS observations (July 2002 – December 2011).

---

## 1. Model Overview & Administrative Metadata

- **Model Name**: Negative Binomial Active Fire Count Regression (NB2)
- **Model Version**: `firechronicle-nb2-v1.0`
- **Release Date**: November 12, 2026
- **Architecture**: Generalized Linear Model (GLM) with Log-Link Function and Estimated Quadratic Dispersion ($\text{Var}(y \mid \mathbf{x}) = \mu + \alpha \mu^2$)
- **Primary Objective**: Harmonize monthly 50 km block Aqua MODIS active fire detection counts into S-NPP VIIRS-equivalent detection counts.
- **Geographic Scope**: State of Pará, Brazil (`region_id = BR-PA`) exclusively (EPSG:6933, 568 canonical 50 km blocks).
- **Temporal Unit**: 50 km Block $\times$ Calendar Month ($1..12$) $\times$ Diurnal Pass (`D` / `N`).
- **Owner / Author**: Member 2 (Data Scientist), FireChronicle Team.
- **Upstream Input**: Audited NASA FIRMS Aqua MODIS 50 km block aggregations (`model/data/historical/2002` through `2011`).
- **Downstream Consumers**: Backend B Integration Service (Member 4) & Web Dashboard (Member 5).
- **Export Contract**: Rulebook Section 5 14-column Parquet table (`model/estimated_viirs_block_month.parquet`).

---

## 2. Mathematical Formulation & Parameter Estimation

The expected VIIRS S-NPP-equivalent detection count $\mu_i = \mathbb{E}[V_i \mid \mathbf{x}_i]$ is formulated as:

$$\ln(\mu_i) = \beta_0 + \beta_1 \ln(1 + M_i) + \beta_2 \cdot I(\text{Night}_i) + \sum_{m=2}^{12} \beta_m \cdot I(\text{Month}_i = m)$$

$$\widehat{V}_i = \mu_i = \exp\left( \beta_0 + \beta_1 \ln(1 + M_i) + \beta_2 \cdot I(\text{Night}_i) + \sum_{m=2}^{12} \beta_m \cdot I(\text{Month}_i = m) \right)$$

where:
- $M_i$ is the observed Aqua MODIS hotspot count in the block-month pass ($M_i \ge 1$).
- $I(\text{Night}_i)$ is a binary indicator ($1$ for nighttime pass `'N'`, $0$ for daytime pass `'D'`).
- $I(\text{Month}_i = m)$ are monthly dummy indicators relative to the reference month January ($m = 1$, $\beta_1 = 0$).
- Overdispersion is governed by the quadratic variance function $\text{Var}(V_i \mid \mathbf{x}_i) = \mu_i + \alpha \mu_i^2$.

### Final Fitted Parameters (Trained on Full Eligible 2012–2020 Population, $N = 23,010$):
- **Baseline Intercept ($\beta_0$)**: $+1.285556$
- **MODIS Elasticity ($\beta_1$, $\ln(1+M)$)**: $+0.984904$
  *(Demonstrates near-proportional power scaling with slight sub-linearity $\approx M^{0.985}$, capturing sensor saturation at high fire densities).*
- **Nighttime Pass Coefficient ($\beta_2$, Night 'N')**: $+1.243874$
  *(Represents a $\exp(1.243874) \approx 3.47\times$ detection boost for nighttime passes, reflecting VIIRS Day/Night Band sensitivity and superior low-saturation radiance threshold relative to MODIS).*
- **Seasonal Monthly Coefficients ($\beta_m$, baseline Month 1 = 0)**:
  - **Wet Season / Reduced Fire Activity**:
    Month 2 (Feb): $-0.428010$
    Month 3 (Mar): $-0.966056$
    Month 4 (Apr): $-0.843459$
    Month 5 (May): $-0.579079$
    Month 6 (Jun): $-0.236715$
  - **Amazon Dry Burning Season / Elevated Fire Activity**:
    Month 7 (Jul): $+0.005950$
    Month 8 (Aug): $+0.281541$
    Month 9 (Sep): $+0.277136$
    Month 10 (Oct): $+0.348436$
    Month 11 (Nov): $+0.195999$
    Month 12 (Dec): $+0.214385$
- **Dispersion Parameter ($\alpha$)**: $0.339430$
- **Optimization Convergence**: Maximum Likelihood Estimation converged successfully.
- **Log-Likelihood**: $-105,163.79$ ($\text{AIC} = 210,357.58$, $\text{BIC} = 210,478.24$).
- **Full-Population Ratio Baseline**: $k = 6.053847$ ($\sum V / \sum M = 2,072,819 / 342,397$, calibrated on all $23,010$ clean paired-positive records).

---

## 3. Independent Validation Provenance & Empirical Holdout Benchmarks

Validation metrics from strictly held-out evaluation partitions are tracked separately from final full-training fit statistics.

### Primary Validation Population Definition:
Evaluated strictly on **clean paired-positive satellite detection records** ($M > 0$ and $V > 0$, $N = 23,010$ records across 2012–2020 after excluding truncated January 2012). It does **not** evaluate unobserved or cloud-covered landscape cells ($78,961$ full-panel unobserved records).

### Benchmark Matrix:

| Evaluation Strategy | Split Protocol | Performance Metric | Model 0 (Ratio Baseline) | Model 1 (Negative Binomial NB2) | Performance Delta |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Strategy A: Temporal Holdout** | **Train:** 2012–2018 ($N = 17,919$)<br>**Test:** 2019–2020 ($N = 5,091$) | **Mean Absolute Error (MAE)**<br>**Mean Poisson Deviance**<br>**Aggregate Count Bias**<br>**Monthly Profile Correlation** | 44.9884<br>55.3136<br>-12.91%<br>0.9854 | **35.4374**<br>**25.0056**<br>**-11.50%**<br>**0.9772** | **-21.2% MAE**<br>**-54.8% Deviance**<br>+1.41% Bias<br>Stable |
| **Strategy B: Geographic Holdout** | **Train:** 80% Blocks ($N = 17,863$)<br>**Test:** 20% Blocks ($N = 5,147$) | **Mean Absolute Error (MAE)**<br>**Mean Poisson Deviance**<br>**Aggregate Count Bias**<br>**Monthly Profile Correlation** | 53.8686<br>56.3544<br>-4.38%<br>0.9926 | **35.7903**<br>**20.9497**<br>**+4.55%**<br>**0.9936** | **-33.6% MAE**<br>**-62.8% Deviance**<br>Near-zero bias<br>Stable |

### Zero-Imputation Sensitivity Analysis (Experimental, Not Production Policy):
When evaluating the subset of records where S-NPP VIIRS detected active fires but Aqua MODIS recorded no detections ($M = 0$, $N = 4,168$ in 2019–2020 test set):
- **Ratio Baseline**: Predicts $\widehat{V} = k \cdot 0 = 0$ everywhere, resulting in an exact **-100.00% aggregate bias** and deviance of $306.21$.
- **Negative Binomial NB2**: Produces non-zero seasonal/diurnal baseline expectations ($\mu \approx 3.6$ to $7.2$), yielding $+5.19\%$ aggregate bias and deviance of $8.60$.
- *Caveat*: While statistically informative, zero imputation is explicitly treated as a sensitivity experiment. Production inference prohibits converting missing MODIS counts to zero.

---

## 4. Historical Inference Summary (July 2002 – December 2011)

The frozen NB2 model was applied to generate the official public historical handoff table:

- **Total Export Panel Size**: **129,504 canonical records** ($568 \text{ blocks} \times 114 \text{ months} \times 2 \text{ diurnal passes}$).
- **Eligible Positive Estimations ($M > 0$)**: **26,962 records** ($100\%$ of all positive historical detections).
  - Total Historical Aqua MODIS Hotspots: **617,948 detections**.
  - Total Estimated VIIRS S-NPP-Equivalent Count: **3,557,995.78 detections**.
  - Overall Implied Multiplier: **5.7578** (reflecting diurnal and seasonal weighting).
  - Minimum Non-Zero Prediction: **2.72**; Maximum Prediction: **6,493.95**; Median: **46.68**.
- **Preserved NULL Records**: **102,542 records** preserved strictly as `NULL` / `NaN` with `prediction_status = "missing_required_feature"`.
- **Pre-Aqua Exclusions (Jan–Jun 2002)**: $6,816$ unobservable pre-Aqua records ($568 \times 6 \times 2$) were excluded from the public historical export.
- **July 2002 Source Limitation**: Explicitly designated as a partial-month source observation period (NASA Aqua MODIS regular scientific telemetry commenced July 4, 2002).

---

## 5. Backend Schema Contract Compliance

The output table matches the 14-column backend handoff specification:

| Field Name | Data Type | Specification / Approved Values | Example |
| :--- | :--- | :--- | :--- |
| `region_id` | string | Strictly `"BR-PA"` (Pará state) | `"BR-PA"` |
| `block_id` | string | Canonical `bx_by` EPSG:6933 format | `"-100_-10"` |
| `block_ix` | int64 | Projected X index in 50 km grid | `-100` |
| `block_iy` | int64 | Projected Y index in 50 km grid | `-10` |
| `year` | int64 | Calendar year ($2002 \dots 2011$) | `2005` |
| `month` | int64 | Calendar month ($7 \dots 12$ for 2002; $1 \dots 12$ for 2003–2011) | `9` |
| `daynight` | string | Strictly diurnal pass indicator (`"D"` or `"N"`) | `"D"` |
| `estimated_viirs_count` | float64 | Non-negative estimated count (or `NULL` / `NaN`) | `144.25` |
| `value_type` | string | Strictly `"estimated"` (Rulebook Section 5 contract) | `"estimated"` |
| `prediction_status` | string | `"ok_preliminary"` (for $M > 0$) or `"missing_required_feature"` (for NULL) | `"ok_preliminary"` |
| `coverage_status` | string | Preserved from source inputs (`"unknown"`) | `"unknown"` |
| `model_version` | string | Strictly `"firechronicle-nb2-v1.0"` | `"firechronicle-nb2-v1.0"` |
| `measurement_unit` | string | Strictly `"VIIRS_S-NPP-equivalent_detection_count"` | `"VIIRS_S-NPP-equivalent_detection_count"` |
| `calibration_scale_km` | int64 | Strictly `50` (50 km grid resolution) | `50` |

---

## 6. Scientific Limitations & Responsible AI Notice

1. **Conditional on MODIS Detections**: The Negative Binomial model is trained on paired-positive observations. It estimates expected VIIRS counts conditional on Aqua MODIS detecting active fire ($M \ge 1$). It cannot independently detect fires that were unobserved by Aqua MODIS due to cloud cover, smoke occlusion, or satellite overpass timing.
2. **Detection Absence is Not Proof of Fire Absence**: A NULL prediction indicates an absence of input MODIS detections or unverified telemetry, not confirmed zero fire activity.
3. **Not Ground-Truth Burned Area**: Predictions represent equivalent active fire pixel detection counts, not physical burned area (hectares), flame front perimeter, or total carbon emission tonnage.
4. **No Synthetic VIIRS Fabrication**: Historical estimates must always be labeled with `value_type = "estimated"`. They must never be presented to end users or decision-makers as actual empirical S-NPP VIIRS satellite observations.
