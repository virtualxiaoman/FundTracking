import http from './http'

// 首页持仓卡片（含估值/净值）
export const getPortfolio = (force = false) => http.get('/portfolio', { params: { force } })

// 持仓管理
export const listHoldings = () => http.get('/holdings')
export const addHolding = (fundCode) => http.post('/holdings', { fund_code: fundCode })
export const removeHolding = (fundCode) => http.delete(`/holdings/${fundCode}`)
export const setAmount = (fundCode, currentAmount, profitAmount) =>
  http.put(`/holdings/${fundCode}/amount`, { current_amount: currentAmount, profit_amount: profitAmount })
export const addTransaction = (fundCode, txnDate, amount, updateAmount = true) =>
  http.post(`/holdings/${fundCode}/transactions`, { date: txnDate, amount, update_amount: updateAmount })

// 基金信息
export const searchFunds = (keyword, limit = 15) =>
  http.get('/funds/search', { params: { keyword, limit } })

// 历史净值曲线
export const getHistory = (fundCode, range) =>
  http.get(`/funds/${fundCode}/history`, { params: { range } })

// 全部基金排行
export const getRanking = (range, sort = 'desc', limit = 50) =>
  http.get('/ranking', { params: { range, sort, limit } })
