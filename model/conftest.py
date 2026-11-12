"""Pytest configuration and environment shims for FireChronicle model workspace."""
import pandas as pd

try:
    import pyarrow.parquet
except Exception:
    try:
        import fastparquet
    except Exception:
        import duckdb

        _orig_read_parquet = pd.read_parquet

        def _safe_read_parquet(path, *args, **kwargs):
            try:
                return _orig_read_parquet(path, *args, **kwargs)
            except Exception:
                return duckdb.read_parquet(str(path)).df()

        pd.read_parquet = _safe_read_parquet

        _orig_to_parquet = pd.DataFrame.to_parquet

        def _safe_to_parquet(self, path, *args, **kwargs):
            try:
                return _orig_to_parquet(self, path, *args, **kwargs)
            except Exception:
                p = str(path).replace('\\', '/')
                duckdb.sql(f"COPY self TO '{p}' (FORMAT PARQUET)")

        pd.DataFrame.to_parquet = _safe_to_parquet
