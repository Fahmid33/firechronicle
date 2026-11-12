# Synthetic Datasets Notice

The files in this directory contain **artificially generated mock data**:

1. **`synthetic_overlap_BR-PA.csv`**:
   - Initial 22-row synthetic test fixture used for the Ratio-of-Totals baseline model and handoff testing.
2. **`synthetic_nb_training_BR-PA.csv`**:
   - 288-row synthetic test fixture across years 2018–2020, 12 months, day/night passes, and 4 blocks.
3. **`synthetic_eval_multiblock_BR-PA.csv`**:
   - 576-row multi-block, multi-year synthetic evaluation fixture across 6 blocks (`120_-50`, `121_-50`, `122_-50`, `120_-51`, `121_-51`, `122_-51`) and 4 years (2017–2020).
   - Designed specifically for genuine independent **temporal holdout** (train 2017–2019, test 2020) and **geographic holdout** (train 4 blocks, test 2 disjoint blocks).

---

### Key Guardrails
- **Canonical Block IDs (`block_id`)**: Block IDs follow the project's canonical `"bx_by"` string format (e.g., `"120_-50"`, `"121_-51"`). **Important**: These are purely synthetic test identifiers and are **not** derived from actual Pará geographic coordinates.
- **Coverage Status (`coverage_status = "unknown"`)**: In line with the rulebook, FIRMS fire-positive records without separate clear-sky/cloud proof are treated as coverage-unadjusted. The `"unknown"` status indicates that usable observation coverage has not been independently verified; it does **not** signify a verified zero-fire or clear-sky observation.
- **Disclaimer**: These counts are **not** real NASA MODIS or VIIRS observational data and must not be used for scientific conclusions or operational wildfire reporting.
