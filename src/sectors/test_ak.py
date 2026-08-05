import akshare as ak

from src.config.path import SECTORS_DIR

df = ak.fund_etf_spot_em()
print(df)
CSV_PATH = SECTORS_DIR / "fund_etf_spot_em.csv"
print(CSV_PATH.resolve())
df.to_csv(CSV_PATH, index=False)
