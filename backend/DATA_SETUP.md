## Backend Data Directory Layout (ackend/data/)

Large `.parquet` files are excluded from Git. Place the frozen Data Science artifacts in the following exact paths before starting the API or running tests:

- `backend/data/estimated_viirs_block_month.parquet` (Frozen NB2 v1.0 historical predictions, 2002-07 to 2011-12, 129,504 rows, 14 cols)
- `backend/data/model_info.json` (Copy of `model_info_final_nb2.json`, tracked in Git)
- `backend/data/validation_metrics.json` (Copy of `validation_metrics_final_nb2.json`, tracked in Git)
- `backend/data/para_50km_grid_canonical.parquet`, `para_50km_grid_geometry.parquet`, `para_boundary.geojson`
- `backend/data/real/2012..2020/` (Authoritative 2012-2020 observed archive: 344,071 MODIS / 2,196,531 VIIRS)

## Local Run & Verification (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
$env:APP_ENV = "production"
.\.venv\Scripts\python.exe scripts\run_all_tests.py
Remove-Item Env:APP_ENV
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
