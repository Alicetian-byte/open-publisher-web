import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

/** localStorage 持久化 state：布局宽度 / 分栏比例等用户偏好跨会话保留。 */
export function usePersistentState<T>(
  key: string,
  initial: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // 存储不可用时静默降级为会话内状态
    }
  }, [key, value]);
  return [value, setValue];
}
