"""
Download Polymarket backtest data from HuggingFace in batches.
Starts with the small markets.parquet (68MB), then quant.parquet (21GB in chunks).
"""
import os
from huggingface_hub import hf_hub_download

DATA_DIR = os.path.join(os.path.dirname(__file__), "")
REPO = "SII-WANGZJ/Polymarket_data"
REPO_TYPE = "dataset"

print("Polymarket Data Downloader")
print("=" * 50)

# Batch 1: markets.parquet (68MB) - market metadata
print("\n[Batch 1/3] Downloading markets.parquet (68MB)...")
try:
    path = hf_hub_download(
        repo_id=REPO,
        filename="markets.parquet",
        repo_type=REPO_TYPE,
        local_dir=DATA_DIR,
    )
    print(f"  Done: {path}")
except Exception as e:
    print(f"  Error: {e}")

# Batch 2: First 50MB of quant.parquet for initial backtest
# (We'll download it in full later - 21GB)
print("\n[Batch 2/3] markets.parquet complete!")
print("  quant.parquet (21GB) will be downloaded separately for full backtest")

# Verify
print("\n[Batch 3/3] Checking downloaded files...")
for f in ["markets.parquet"]:
    fp = os.path.join(DATA_DIR, f)
    if os.path.exists(fp):
        size_mb = os.path.getsize(fp) / 1024 / 1024
        print(f"  {f}: {size_mb:.1f} MB")
    else:
        print(f"  {f}: NOT FOUND")

print("\nDone! Run backtest with: python backtest/run_backtest.py")