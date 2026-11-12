# FireChronicle Provisional Model Card — Negative Binomial (NB2) Hotspot Harmonization

> [!IMPORTANT]
> **PROVISIONAL SCIENTIFIC CALIBRATION ARTIFACT — FOR TEAM LEADER & REPO DOCUMENTATION**
> This model card documents the empirically calibrated and validated **Negative Binomial (NB2) Harmonization Model** evaluated across the complete 9-year NASA FIRMS overlap collection (2012–2020) for Pará, Brazil. Production export awaits upstream delivery of historical pre-2012 Aqua MODIS observations.

---

## 1. Model Details

- **Model Name**: Negative Binomial Count Regression (NB2)
- **Model Identifier**: `firechronicle-nb2-provisional-v1.0`
- **Model Type**: Generalized Linear Model (GLM) with Log-Link Function and Quadratic Variance Specification
- **Primary Function**: Harmonizes monthly 50 km block Aqua MODIS active fire detection counts into S-NPP VIIRS-equivalent detection counts.
- **Geographic Domain**: State of Pará, Brazil (`region_id = BR-PA`) exclusively (EPSG:6933, 568 canonical 50 km blocks).
- **Temporal Modeling Unit**: 50 km Block $\times$ Calendar Year $\times$ Month ($1..12$) $\times$ Diurnal Pass (`D` / `N`).
- **Owner**: Member 2 (Data Scientist), FireChronicle Team.
- **Upstream Data**: Cleaned NASA FIRMS Aqua MODIS & S-NPP VIIRS 50 km block aggregations from Member 1 (Data Engineer).
- **Downstream Consumer**: Backend B Service (Member 4) & Web Dashboard (Member 5).

---

## 2. Mathematical Formulation

The expected S-NPP VIIRS equivalent count $\mu_i = \mathbb{E}[V_i \mid \mathbf{x}_i]$ is modeled as:

$$\ln(\mu_i) = \beta_0 + \beta_1 \ln(1 + M_i) + \beta_2 \cdot I(\text{Night}_i) + \sum_{m=2}^{12} \beta_m \cdot I(\text{Month}_i = m)$$

$$\widehat{V}_i = \mu_i = \exp\left( \beta_0 + \beta_1 \ln(1 + M_i) + \beta_2 \cdot I(\text{Night}_i) + \sum_{m=2}^{12} \beta_m \cdot I(\text{Month}_i = m) \right)$$

where:
- $M_i$ is the observed Aqua MODIS hotspot count in the block-month-pass.
- $I(\text{Night}_i)$ is a binary indicator ($1$ for nighttime pass `'N'`, $0$ for daytime pass `'D'`).
- $I(\text{Month}_i = m)$ are monthly indicator dummy variables relative to January ($m=1$).
- Overdispersion is parameterized as $\text{Var}(V_i \mid \mathbf{x}_i) = \mu_i + \alpha \mu_i^2$, with $\alpha \approx 0.33$.

### Fitted Parameters (Calibrated on 2012–2018 Clean Paired Baseline, $N = 17,919$):
- **Baseline Intercept ($\beta_0$)**: $+1.3186$
- **MODIS Elasticity ($\beta_1$, $\ln(1+M)$)**: $+0.9832$
- **Nighttime Diurnal Coefficient ($\beta_2$, Night 'N')**: $+1.2618$
  *(Represents a $\exp(1.2618) \approx 3.53\times$ multiplicative detection boost for nighttime passes, reflecting VIIRS's superior low-saturation dynamic range).*
- **Seasonal Coefficients ($\beta_m$, relative to January $\beta_1 = 0$)**:
  - Wet Season (Feb–May): $\beta_2 = -0.3849, \beta_3 = -0.9815, \beta_4 = -0.8408, \beta_5 = -0.6208$
  - Transition (Jun–Jul): $\beta_6 = -0.2665, \beta_7 = -0.0582$
  - Amazon Dry Burning Season (Aug–Nov): $\beta_8 = +0.1597, \beta_9 = +0.2193, \beta_{10} = +0.3068, \beta_{11} = +0.1703, \beta_{12} = +0.1784$

---

## 3. Validation Strategy & Empirical Benchmark Results

Evaluated against the baseline Ratio-of-Totals model ($M_0: \widehat{V} = k \cdot M$) across two independent holdout experiments.

> [!NOTE]
> **Primary Validation Population Definition**:
> Evaluated strictly on **paired-positive satellite detection records** where both sensors recorded positive counts ($M > 0$ and $V > 0$, $N = 23,010$ clean records). It does **not** represent the unobserved or cloud-covered landscape ($78,961$ full-panel unobserved records).

### Benchmark Matrix:

| Evaluation Strategy | Split Design | Performance Metric | Model 0 (Ratio Baseline) | Model 1 (Negative Binomial NB2) | Performance Delta |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Strategy A: Out-of-Time Temporal Holdout** | **Train**: 2012–2018 ($N = 17,919$)<br>*(Month 1, 2012 excluded)*<br>**Test**: 2019–2020 ($N = 5,091$) | **Fitted Parameter** | $k = 5.8696$ | $\alpha = 0.3290$ (Converged) | — |
| | | **Mean Absolute Error (MAE)** | 44.9884 | **35.4374** | **-21.2% Error Reduction** |
| | | **Mean Poisson Deviance** | 55.3136 | **25.0056** | **-54.8% Deviance Reduction** |
| | | **Total Poisson Deviance** | 281,601.8 | **127,303.6** | **-54.8% Deviance Reduction** |
| | | **Aggregate Count Bias %** | -12.91% | **-11.50%** | **+1.41% Less Biased** |
| | | **Monthly Profile Correlation ($r$)** | **0.9854** | 0.9772 | High Seasonal Fidelity |
| | | *— 2019 Held-Out Year MAE* | 39.4542 | **28.8864** | **-26.8% Error Reduction** |
| | | *— 2019 Aggregate Bias %* | **-2.98%** | -3.26% | Unbiased Generalization |
| | | *— 2020 Held-Out Year MAE* | 50.2615 | **41.6794** | **-17.1% Error Reduction** |
| | | *— 2020 Aggregate Bias %* | -19.96% | **-17.36%** | Superior in Extreme Drought |
| **Strategy B: Spatial Cross-Validation** | **Train**: 376 Blocks ($80\%$, $N = 17,863$)<br>**Test**: 94 Blocks ($20\%$, $N = 5,147$) | **Fitted Parameter** | $k = 5.9849$ | $\alpha = 0.3470$ (Converged) | — |
| | | **Mean Absolute Error (MAE)** | 53.8686 | **35.7903** | **-33.6% Error Reduction** |
| | | **Mean Poisson Deviance** | 56.3544 | **20.9497** | **-62.8% Deviance Reduction** |
| | | **Total Poisson Deviance** | 290,056.0 | **107,828.2** | **-62.8% Deviance Reduction** |
| | | **Aggregate Count Bias %** | -4.38% | **+4.55%** | Controlled ($<5\%$) |
| | | **Monthly Profile Correlation ($r$)** | 0.9926 | **0.9936** | **Superior Alignment** |

---

## 4. Sensitivity Analysis: Imputed Zero-MODIS Detections

To evaluate model stability when VIIRS detects fires but MODIS records no hotspot ($N = 18,747$ clean records in 2012–2020), an exploratory sensitivity experiment was conducted setting $M = 0$:

- **Isolated Zero-MODIS Test Subset ($N = 4,168$ records in 2019–2020, observed VIIRS $= 28,486$, average observed $= 6.83$ detections/record)**:
  - **Model 0 (Ratio Baseline)**: Predicts $\widehat{V} = 0.00$ everywhere (average predicted $= 0.00$ detections/record). Aggregate bias is **$-100.00\%$**, MAE $= 6.8345$, and Mean Poisson Deviance $= 306.2053$.
  - **Model 1 (Negative Binomial)**: Predicts non-zero baseline conditioned on month and diurnal pass. Total predicted sum $= \mathbf{29,964.01}$ (average predicted $= \mathbf{7.19}$ detections/record vs observed average of $6.83$), producing **$+5.19\%$ aggregate bias**, MAE $= 6.2107$, and Mean Poisson Deviance $= 8.5952$.
- **Combined Test Set ($N = 9,259$ records, observed VIIRS $= 517,222$, average observed $= 55.86$ detections/record)**:
  - Model 0 combined bias is **$-12.78\%$** ($451,104.38$ total predicted, average $= 48.72$ detections/record when trained on combined data) or **$-17.71\%$** ($425,637.09$ total predicted, average $= 45.97$ detections/record using paired $k = 5.8696$).
  - Model 1 combined bias is **$-9.67\%$** ($467,222.06$ total predicted, average $= 50.46$ detections/record; combined MAE $= 21.6859$).

> [!WARNING]
> **Sensitivity Disclaimer & Missing-to-Zero Assumptions**:
> Missing-to-zero conversions ($M = 0$) are strictly **exploratory experimental assumptions** evaluated solely for sensitivity analysis. They do **not** represent validated satellite coverage or clear-sky ground observation proof. In accordance with Rulebook Section 3, unobserved cells must remain `<NA>` in data stores and are **not** approved for automated production zero-imputation without independent atmospheric/cloud-clearing verification.

---

## 5. Scope of Provisional Recommendation & Landscape Invariants

> [!IMPORTANT]
> **Landscape Scope Guardrail**:
> The provisional recommendation of Model 1 (Negative Binomial NB2) applies strictly to the **observed paired-positive detection subpopulation** ($M > 0$ and $V > 0$). It does **not** imply scientifically validated estimates across the entire landscape (which includes $78,961$ full-panel unobserved/cloud-covered records). Extrapolation to unobserved blocks remains unvalidated without external cloud-clearing confirmation.

1. **Attribution of Missing Detections**: The fact that Aqua MODIS has missing detections in a block where S-NPP VIIRS detected active fire does **not** prove that fires were missed solely due to spatial resolution ($1\text{ km}$ vs $375\text{ m}$). Ephemeral cloud cover, off-nadir viewing geometry (scan-edge pixel expansion), and minute-to-hour differences in overpass timing relative to short-lived fire combustion all contribute to detection discordance.
2. **True Zero Extrapolation**: Neither model can determine whether a zero observation in historical data was a clear-sky fire-free condition or cloud-obscured data loss without external cloud-mask rasters.
3. **Extreme Climate Spikes**: In 2020, unprecedented Amazon burning conditions drove the empirical domain ratio to $k = 7.70$. Models trained on multi-year baselines ($k \approx 5.87$) underpredict such extreme years by $15–20\%$. Predictions must be interpreted as expected multi-year climatological equivalents.

---

## 6. Pre-2012 Historical Data Status

- Real empirical Aqua MODIS observations for **July 2002 through December 2011** have not yet been delivered to the workspace.
- **Scientific Guardrail**: In strict adherence to scientific integrity, **no pre-2012 predictions have been generated or fabricated**. Historical estimation will execute once genuine pre-2012 MODIS 50 km block aggregations are delivered by the Data Engineer.
