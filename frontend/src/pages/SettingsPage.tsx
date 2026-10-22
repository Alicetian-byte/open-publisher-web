import { Monitor, Moon, Sun } from "lucide-react";
import { useThemeSetting, type ThemeSetting } from "../lib/theme";

// 用户设置页：只包含普通用户可配置项（外观主题等）。
// 模型/API 配置已移至管理端（frontend-admin），普通用户不接触密钥与接入信息。

export default function SettingsPage() {
  const { setting: themeSetting, setSetting: setThemeSetting } = useThemeSetting();

  return (
    <div className="settings-page" style={{ padding: "20px 24px", display: "grid", gap: 16, maxWidth: 760 }}>
      <div>
        <p className="page-kicker">设置</p>
        <h1>设置</h1>
      </div>

      <div className="panel" style={{ display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0 }}>外观</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(
            [
              { id: "light", label: "浅色", icon: Sun },
              { id: "dark", label: "深色", icon: Moon },
              { id: "system", label: "跟随系统", icon: Monitor },
            ] as Array<{ id: ThemeSetting; label: string; icon: typeof Sun }>
          ).map(({ id, label, icon: Icon }) => (
            <button
              aria-pressed={themeSetting === id}
              className={`button ${themeSetting === id ? "button--primary" : "button--quiet"}`}
              key={id}
              onClick={() => setThemeSetting(id)}
              type="button"
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          跟随系统时自动响应操作系统的明暗设置；选择立即生效并记忆。
        </p>
      </div>

      <div className="panel" style={{ display: "grid", gap: 8 }}>
        <h2 style={{ margin: 0 }}>模型与接入</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          写作模型与 API 接入由管理员在管理端统一配置，普通用户无需手动设置。
          如需更换模型或排查连通问题，请联系管理员。
        </p>
      </div>
    </div>
  );
}
