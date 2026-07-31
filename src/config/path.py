from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

ASSETS_DIR = PROJECT_ROOT / "assets"
DATA_DIR = PROJECT_ROOT / "data"
FUNDS_DIR = DATA_DIR / "funds"

FUND_LIST_CACHE_PATH = FUNDS_DIR / "info/fund_list_cache.pkl"

if __name__ == "__main__":
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"数据目录：{DATA_DIR}")
    print(f"基金目录：{FUNDS_DIR}")
