import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useAdminAuth } from "./AuthContext";
import { WhaleLoginBackdrop } from "./components/WhaleLoginBackdrop";
import SpecularFrame from "./components/SpecularFrame";
import CursorGrid from "./components/CursorGrid";
import "./components/LoginBackdrop.css";
import "./AdminLoginPage.css";

export default function AdminLoginPage() {
  const { login } = useAdminAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await login(form.username, form.password);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "登录失败。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="admin-login auth-page">
      <WhaleLoginBackdrop />
      <form
        className="admin-card auth-card"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}>
        <SpecularFrame
          radius={18}
          lineColor="#d8eaff"
          baseColor="#647f9e"
          intensity={0.85}
          idleIntensity={0.2}
          shineSize={12}
          shineFade={40}
          thickness={1.2}
          glow={0.45}
          followMouse
          proximity={220}
        />
        <CursorGrid
          className="auth-card-grid"
          cellSize={44}
          color="#b6d9ff"
          gridColor="#a4bfdc"
          radius={130}
          maxOpacity={0.28}
          fillOpacity={0.035}
          gridOpacity={0.045}
          spotlight={0.22}
          holdTime={180}
          fadeDuration={1000}
          edgeFade={0.12}
          dpr={1.5}
          clickPulse={false}
          intro={false}
        />
        <div className="admin-brand">
          <ShieldCheck size={20} />
          <strong>稿流管理控制台</strong>
        </div>
        <label>
          <span>管理员账号</span>
          <input
            autoComplete="username"
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
            value={form.username}
          />
        </label>
        <label>
          <span>密码</span>
          <input
            autoComplete="current-password"
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            type="password"
            value={form.password}
          />
        </label>
        <button className="primary" disabled={busy} type="submit">{busy ? "登录中..." : "登录管理端"}</button>
        {error && <div className="error">{error}</div>}
      </form>
    </main>
  );
}
