import duckdb

print("=== 2. DATA CONSTRAINTS VERIFICATION (SPARSE-TO-DENSE JOIN) ===")
conn = duckdb.connect()

# 1. Load the DE's normalized files
conn.execute("CREATE VIEW canonical AS SELECT * FROM 'data/para_50km_grid_canonical.parquet'")
conn.execute("CREATE VIEW master_sparse AS SELECT * FROM 'data/firechronicle_master_2012.parquet'")

# 2. Reconstruct the dense grid (568 blocks x 12 months x 2 Day/Night periods = 13,632 rows)
conn.execute("""
    CREATE VIEW full_dense_panel AS
    SELECT 
        c.block_id, 
        2012 AS year, 
        m.month, 
        dn.daynight
    FROM canonical c
    CROSS JOIN (SELECT UNNEST(GENERATE_SERIES(1, 12)) AS month) m
    CROSS JOIN (SELECT UNNEST(['D', 'N']) AS daynight) dn
""")

# 3. LEFT JOIN the sparse fire data onto the dense map grid
conn.execute("""
    CREATE VIEW final_backend_view AS
    SELECT 
        f.block_id, f.year, f.month, f.daynight,
        s.modis_count, s.viirs_count
    FROM full_dense_panel f
    LEFT JOIN master_sparse s
        ON f.block_id = s.block_id 
       AND f.month = s.month 
       AND f.daynight = s.daynight
""")

# Verify Totals
modis_total = conn.execute("SELECT SUM(modis_count) FROM final_backend_view").fetchone()[0]
viirs_total = conn.execute("SELECT SUM(viirs_count) FROM final_backend_view").fetchone()[0]
print(f"MODIS Total: {modis_total} (Expected: 41074)")
print(f"VIIRS Total: {viirs_total} (Expected: 243498)")

# Verify exactly reconstructed NULLs
modis_nulls = conn.execute("SELECT COUNT(*) FROM final_backend_view WHERE modis_count IS NULL").fetchone()[0]
viirs_nulls = conn.execute("SELECT COUNT(*) FROM final_backend_view WHERE viirs_count IS NULL").fetchone()[0]
print(f"\nMODIS NULL count: {modis_nulls} (Expected: 11024)")
print(f"VIIRS NULL count: {viirs_nulls} (Expected: 9114)")

# Verify strict map integrity
blocks = conn.execute("SELECT COUNT(DISTINCT block_id) FROM final_backend_view").fetchone()[0]
print(f"\nUnique 50km Blocks: {blocks} (Expected: 568)")

if modis_nulls == 11024 and viirs_nulls == 9114 and blocks == 568:
    print("\n✅ ALL CONSTRAINTS VERIFIED! The relational join perfectly preserved the grid and NULLs.")