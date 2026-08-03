"""
持仓数据存储仓库。

职责:
- 持有基金列表 (fund_code, current_amount, profit_amount)
- 每只基金的增减仓流水记录 (date, amount)

说明:
- 持仓数据存于 data/portfolio/holdings.json
- 完全独立于 src/funds、src/config 下的已有代码
"""

from __future__ import annotations

import copy
import json
import threading

from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from src.config.path import PORTFOLIO_DIR

DATA_FILE = PORTFOLIO_DIR / "holdings.json"


@dataclass(slots=True)
class Transaction:
    """一条增减仓记录"""
    date: str
    amount: float


@dataclass(slots=True)
class FundHolding:
    """一只基金的持仓"""
    fund_code: str
    current_amount: float = 0.0
    profit_amount: float = 0.0
    transactions: list[Transaction] = field(default_factory=list)


class HoldingsRepository:
    """持仓仓库（JSON 存储，线程安全）"""

    def __init__(self, path: Path = DATA_FILE):
        self._path = path
        self._lock = threading.RLock()
        self._holdings: dict[str, FundHolding] = {}
        self._load()

    # ==========================================================
    # Python协议
    # ==========================================================
    def __contains__(self, fund_code: str) -> bool:
        return fund_code.strip() in self._holdings

    def __len__(self) -> int:
        return len(self._holdings)

    # ==========================================================
    # 查询
    # ==========================================================
    def list(self) -> list[FundHolding]:
        """ 返回全部持仓（基金代码升序）。 返回的是深拷贝，外部修改不会影响仓库。 """
        with self._lock:
            return [copy.deepcopy(self._holdings[code]) for code in sorted(self._holdings)]

    def get(self, fund_code: str) -> FundHolding | None:
        """ 获取指定基金持仓。 返回深拷贝。 """
        with self._lock:
            holding = self._holdings.get(fund_code.strip())
            if holding is None:
                return None
            return copy.deepcopy(holding)

    def contains(self, fund_code: str) -> bool:
        """ 是否存在该基金。 """
        return fund_code in self

    def get_transactions(self, fund_code: str) -> list[Transaction] | None:
        """ 获取指定基金全部流水。 返回深拷贝。 """
        with self._lock:
            holding = self._holdings.get(fund_code.strip())
            if holding is None:
                return None
            return copy.deepcopy(holding.transactions)

    # ==========================================================
    # 修改
    # ==========================================================
    def add_fund(self, fund_code: str) -> bool:
        """
        新增基金。
        Returns: True: 新增成功 False: 已存在
        """
        with self._lock:
            code = fund_code.strip()

            if not code or code in self._holdings:
                return False

            self._holdings[code] = FundHolding(fund_code=code)
            self._save()
            return True

    def remove_fund(self, fund_code: str) -> bool:
        """ 删除基金及其全部流水。 """
        with self._lock:
            code = fund_code.strip()

            if code not in self._holdings:
                return False

            del self._holdings[code]
            self._save()
            return True

    def set_amount(self, fund_code: str, current_amount: float, profit_amount: float, ) -> bool:
        """ 修改当前持仓金额和收益金额。 """
        with self._lock:
            holding = self._holdings.get(fund_code.strip())

            if holding is None:
                return False

            holding.current_amount = float(current_amount)
            holding.profit_amount = float(profit_amount)

            self._save()
            return True

    def add_transaction(self, fund_code: str, txn_date: date | str, amount: float, ) -> bool:
        """
        添加一条增减仓记录。amount: >0 加仓, <0 减仓
        """
        with self._lock:
            holding = self._holdings.get(fund_code.strip())

            if holding is None:
                return False

            if isinstance(txn_date, date):
                txn_date = txn_date.isoformat()

            holding.transactions.append(Transaction(date=str(txn_date), amount=float(amount)))
            holding.transactions.sort(key=lambda t: t.date)  # 保持按日期排序
            self._save()
            return True

    def clear_transactions(self, fund_code: str) -> bool:
        """ 清空指定基金的全部流水。 """
        with self._lock:
            holding = self._holdings.get(fund_code.strip())
            if holding is None:
                return False
            holding.transactions.clear()
            self._save()
            return True

    # ==========================================================
    # 存储
    # ==========================================================
    def _load(self) -> None:
        """ 从 JSON 加载全部持仓。 """
        if not self._path.exists():
            self._holdings = {}
            return

        try:
            with self._path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            holdings = raw.get("holdings", [])
            if not isinstance(holdings, list):
                holdings = []
            self._holdings.clear()
            for item in holdings:
                code = str(item.get("fund_code", "")).strip()
                if not code:
                    continue
                transactions = []
                for t in item.get("transactions", []):
                    transactions.append(Transaction(date=str(t.get("date", "")), amount=float(t.get("amount", 0.0))))

                transactions.sort(key=lambda x: x.date)

                self._holdings[code] = FundHolding(fund_code=code,
                                                   current_amount=float(item.get("current_amount", 0.0)),
                                                   profit_amount=float(item.get("profit_amount", 0.0)),
                                                   transactions=transactions, )
            self._holdings = dict(sorted(self._holdings.items()))  # 保证内部按基金代码排序（方便调试）

        except Exception as e:
            print(f"[HoldingsRepository] 加载持仓失败: {e}")
            self._holdings = {}

    def _save(self) -> None:
        """ 保存到 JSON。 使用临时文件保证写入安全。 """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"holdings": [asdict(self._holdings[code]) for code in sorted(self._holdings)]}
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    # ==========================================================
    # 公共存储接口
    # ==========================================================
    def save(self) -> None:
        """ 手动保存。 """
        with self._lock:
            self._save()

    def reload(self) -> None:
        """ 从磁盘重新加载。 """
        with self._lock:
            self._load()


if __name__ == "__main__":
    repo = HoldingsRepository()

    print("=" * 60)
    print("当前持仓数量：", len(repo))
    print("=" * 60)

    # 清理旧测试数据
    repo.remove_fund("000001")
    repo.remove_fund("000002")

    print("\n新增基金")
    print(repo.add_fund("000001"))
    print(repo.add_fund("000002"))
    print(repo.add_fund("000001"))  # False

    print("\n修改金额")
    repo.set_amount("000001", 10000, 850)
    repo.set_amount("000002", 5000, -120)

    print("\n增加流水")
    repo.add_transaction("000001", "2025-01-01", 3000)
    repo.add_transaction("000001", "2025-02-01", 5000)
    repo.add_transaction("000001", "2025-03-01", -1000)

    repo.add_transaction("000002", date.today(), 5000)

    print("\n查询单个基金")
    holding = repo.get("000001")
    print(asdict(holding) if holding else None)

    print("\n查询流水")
    txns = repo.get_transactions("000001")
    if txns:
        for txn in txns:
            print(asdict(txn))

    print("\n全部持仓")
    for holding in repo.list():
        print(asdict(holding))

    print("\ncontains:")
    print("000001" in repo)
    print("999999" in repo)

    print("\n清空流水")
    repo.clear_transactions("000002")
    print(asdict(repo.get("000002")))

    print("\n删除基金")
    repo.remove_fund("000002")

    print("\n最终持仓")
    for holding in repo.list():
        print(asdict(holding))
