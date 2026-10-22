import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleUserRound, LogIn, LogOut, UserPlus } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

// 参考主流 AI 聊天站：右上角常驻头像入口；未登录点击出「登录/注册」菜单，
// 已登录显示账号信息与退出。访客可先浏览创作界面，创作时再引导登录。
export function AvatarMenu() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const initial = (user?.displayName || user?.username || "").trim().charAt(0).toUpperCase();

  return (
    <div className="avatar-menu" ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={user ? "账号菜单" : "登录或注册"}
        className="avatar-menu__trigger"
        onClick={() => setOpen((v) => !v)}
        title={user ? user.displayName || user.username : "登录 / 注册"}
        type="button"
      >
        {user ? (
          <span aria-hidden="true" className="avatar-menu__avatar">{initial || "·"}</span>
        ) : (
          <CircleUserRound aria-hidden="true" size={22} strokeWidth={1.8} />
        )}
      </button>

      {open && (
        <div className="avatar-menu__panel" role="menu">
          {user ? (
            <>
              <div className="avatar-menu__header">
                <strong>{user.displayName || user.username}</strong>
                <small>@{user.username}{user.role === "admin" ? " · 管理员" : ""}</small>
              </div>
              <button
                className="avatar-menu__item"
                onClick={async () => {
                  setOpen(false);
                  await logout();
                  navigate("/", { replace: true });
                }}
                role="menuitem"
                type="button"
              >
                <LogOut aria-hidden="true" size={15} />
                退出登录
              </button>
            </>
          ) : (
            <>
              <div className="avatar-menu__header">
                <strong>登录稿流</strong>
                <small>登录后同步文章、模板与素材</small>
              </div>
              <button
                className="avatar-menu__item"
                onClick={() => { setOpen(false); navigate("/login"); }}
                role="menuitem"
                type="button"
              >
                <LogIn aria-hidden="true" size={15} />
                登录
              </button>
              <button
                className="avatar-menu__item"
                onClick={() => { setOpen(false); navigate("/login?mode=register"); }}
                role="menuitem"
                type="button"
              >
                <UserPlus aria-hidden="true" size={15} />
                注册新账号
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
