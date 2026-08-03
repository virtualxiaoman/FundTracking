# 基金持仓看板

基于已有后端仓库（基金信息 / 实时估值 / 历史净值）的 Web 前端，Vue3 + Element Plus + ECharts。

## 功能

- **首页**：持仓基金卡片（基金代码、名称、昨日净值、今日估值、今日净值、涨跌幅、持仓与收益金额），点击卡片弹出历史净值曲线图（可切换 近1月 / 近3月 / 近6月 / 近1年 / 近3年 / 近5年 / 全部）。
- **持仓页**：添加基金（按代码/名称搜索）、完全修改（当前金额 + 收益金额）、加仓 / 减仓（日期 + 金额）、删除持仓（确认）。

## 目录结构

```
src/web/app.py                # FastAPI 接口层（只新增，不改动 src/funds、src/config）
src/portfolio/holdings.py     # 持仓存储（JSON 文件，data/portfolio/holdings.json）
web/                          # Vue3 + Vite 前端工程
  src/views/Home.vue          # 首页
  src/views/Holdings.vue      # 持仓页
web/dist/                     # 前端构建产物（npm run build 生成，由后端托管）
```

## 后端接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/api/portfolio?force=` | 首页卡片数据（估值 + 昨日/今日净值 + 持仓） |
| GET  | `/api/holdings` | 持仓列表（轻量，不请求外部数据源） |
| POST | `/api/holdings` | 添加基金 `{fund_code}` |
| DELETE | `/api/holdings/{code}` | 删除持仓 |
| PUT  | `/api/holdings/{code}/amount` | 完全修改 `{current_amount, profit_amount}` |
| POST | `/api/holdings/{code}/transactions` | 增减仓 `{date, amount}`（amount>0 加仓，<0 减仓） |
| GET  | `/api/funds/search?keyword=&limit=` | 基金模糊搜索 |
| GET  | `/api/funds/{code}/history?range=` | 历史净值（1M/3M/6M/1Y/3Y/5Y/ALL） |
| GET  | `/api/funds/{code}/nav` | 单只基金净值/估值 |
| GET  | `/api/health` | 健康检查 |

## 启动

```bash
# 1. 安装后端依赖
pip install -r requirements.txt -r requirements-web.txt

# 2. 构建前端（可选，dist 已随代码提交则跳过）
cd web && npm install && npm run build && cd ..

# 3. 启动服务
python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

浏览器访问 http://127.0.0.1:8000

### 前端开发模式（热更新）

```bash
cd web
npm run dev    # http://localhost:5173，/api 已代理到 127.0.0.1:8000
```

持仓数据保存在 `data/portfolio/holdings.json`，已加入 `.gitignore`。
