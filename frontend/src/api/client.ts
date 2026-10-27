import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  // 生图 / AI 写作等后端调用可能需要 2 分钟以上；普通请求仍在 interceptor 层按需处理。
  timeout: 180000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("opw_access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
