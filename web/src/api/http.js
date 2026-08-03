import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 60000,
})

// 统一错误提示：把后端 detail 抛到前台
http.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const detail = error.response?.data?.detail
    return Promise.reject(new Error(detail || error.message || '请求失败'))
  }
)

export default http
