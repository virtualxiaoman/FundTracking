import os
import datetime
import pandas as pd
import akshare as ak


class FundNAVEstimator:
    """
    实例创建时立即拉取最新“估算净值”数据（基于 ak.fund_em_value_estimation()）。
    使用说明：
        estimator = FundNAVEstimator(save_to_excel=True)
        nav = estimator.get_estimated_nav("161725")
        df = estimator.get_estimated_nav_batch(["161725", "110022"])
    """

    def __init__(self, save_to_excel: bool = False, cache_dir: str = "../../data/funds/estimate"):
        self.save_to_excel = save_to_excel
        self.cache_dir = cache_dir
        # 立即拉取数据（每次创建实例都会拉取一次）
        self.df = self._fetch_latest_data()

        if self.save_to_excel:
            os.makedirs(self.cache_dir, exist_ok=True)
            self._save_current_data()

    def _fetch_latest_data(self) -> pd.DataFrame:
        """
        从 akshare 拉取估算净值数据并标准化列名。
        返回 DataFrame，包含至少这几列（统一为）：code, name, estimated_nav, official_nav（如果存在）
        """
        # 1) 拉取
        try:
            raw = ak.fund_value_estimation_em()
        except Exception as e:
            raise RuntimeError(f"从 AKShare 拉取估值数据失败: {e}")

        if raw is None or raw.empty:
            raise RuntimeError("AKShare 返回空的数据。可能网络/接口变更或当天无估值数据。")

        # 2) 清洗列名（去首尾空格）
        raw.columns = raw.columns.str.strip()
        cols = list(raw.columns)

        # 3) 辅助函数：按关键字寻找列名（更鲁棒）
        def find_col(keywords):
            for c in cols:
                for kw in keywords:
                    if kw in c:
                        return c
            return None

        code_col = find_col(['代码', '基金代码'])
        name_col = find_col(['名称', '基金简称', '简称'])
        # 估算列可能叫：'估算值' / '估算净值' / '估值' / '交易日-估算数据-估算值' 等
        estimated_col = find_col(['估算', '估值', '估算值'])
        # 官方单位净值列可能存在：'单位净值' / '交易日-公布数据-单位净值' 等
        official_col = find_col(['单位净值', '公布数据-单位净值', '官方单位净值'])

        if code_col is None or name_col is None or estimated_col is None:
            # 输出当前列名以便排查
            raise RuntimeError(
                "未能在 AKShare 返回的表头中匹配到需要的列。"
                f" 当前列名包括: {cols}. "
                "期望至少包含类似于 '代码'、'名称'、以及包含 '估算' 或 '估值' 的列。"
            )

        # 4) 重命名为统一列名，便于后续使用
        df = raw.rename(columns={code_col: 'code', name_col: 'name', estimated_col: 'estimated_nav'})
        if official_col:
            df = df.rename(columns={official_col: 'official_nav'})
        else:
            df['official_nav'] = pd.NA  # 若不存在官方单位净值则填 NA

        # 5) 保证需要的列存在并按类型处理
        df = df[['code', 'name', 'estimated_nav', 'official_nav']].copy()

        # 尝试把估算净值转换为 float（如果字符串带逗号、空格、-- 等要先处理）
        def to_float_safe(x):
            try:
                if pd.isna(x):
                    return float('nan')
                # 去掉逗号和空格
                if isinstance(x, str):
                    x = x.replace(',', '').strip()
                    if x in ['', '--', '—']:
                        return float('nan')
                return float(x)
            except Exception:
                return float('nan')

        df['estimated_nav'] = df['estimated_nav'].apply(to_float_safe)
        df['official_nav'] = df['official_nav'].apply(to_float_safe)

        return df

    def _save_current_data(self):
        """
        将当前 DataFrame 保存为 Excel，文件名格式 eg. 26-1-13.csv
        """
        today = datetime.date.today()
        # 格式：两位年份-月-日，如 26-1-13
        today_str = f"{today.year % 100}-{today.month}-{today.day}"
        file_path = os.path.join(self.cache_dir, f"{today_str}.csv")
        try:
            self.df.to_csv(file_path, index=False)
        except Exception as e:
            # 保存失败不影响主流程，但抛出警告（此处用 RuntimeError 便于上层捕获）
            raise RuntimeError(f"保存估值数据到 {file_path} 失败: {e}")

    # ============ 对外查询接口 ============

    def get_estimated_nav(self, fund_code: str) -> float:
        """
        查询单只基金的盘中估算净值（estimated NAV）。
        :param fund_code: 6位基金代码（字符串或数字都支持）
        :return: float（若无估算值会抛出 ValueError）
        """
        code = str(fund_code).strip()
        row = self.df[self.df['code'] == code]
        if row.empty:
            # 也尝试以去掉前导/尾随0的方式匹配（有些数据源 code 可能没有前置0）
            alt_row = self.df[self.df['code'] == code.zfill(6)]
            if not alt_row.empty:
                row = alt_row
        if row.empty:
            raise ValueError(f"未找到基金 {fund_code} 的估算记录（请确认代码是否正确）")

        value = row.iloc[0]['estimated_nav']
        if pd.isna(value):
            raise ValueError(f"基金 {fund_code} 当前无估算净值（estimated NAV）或估值尚未更新")
        return float(value)

    def get_estimated_nav_batch(self, fund_codes: list[str]) -> pd.DataFrame:
        """
        批量查询估算净值，返回包含 code, name, estimated_nav, official_nav 的 DataFrame
        :param fund_codes: 基金代码列表
        """
        codes = [str(c).strip() for c in fund_codes]
        df = self.df[self.df['code'].isin(codes)].copy()
        if df.empty:
            # 尝试使用 zfill 形式再次匹配（防止用户传 '161725' 与数据源 '0161725' 之类差异）
            zcodes = [c.zfill(6) for c in codes]
            df = self.df[self.df['code'].isin(zcodes)].copy()
        if df.empty:
            raise ValueError("未命中任何基金代码，请检查输入列表。")
        return df.reset_index(drop=True)


if __name__ == "__main__":
    # 每次创建实例都会实时拉取一次估值数据
    estimator = FundNAVEstimator(save_to_excel=True)

    # 单只查询
    try:
        nav = estimator.get_estimated_nav("017437")
        print(f"当前预估净值（017437）：{nav:.4f}")
    except Exception as e:
        print("单只查询失败：", e)
    try:
        nav = estimator.get_estimated_nav("007540")
        print(f"当前预估净值（007540）：{nav:.4f}")
    except Exception as e:
        print("单只查询失败：", e)

    # 批量查询
    try:
        df_res = estimator.get_estimated_nav_batch(["018125", "025209"])
        print(df_res)
    except Exception as e:
        print("批量查询失败：", e)
