import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, LoaderCircle, LogIn, UserPlus } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { WhaleLoginBackdrop } from "../components/WhaleLoginBackdrop";
import { CodeSlots } from "../components/CodeSlots";
import HoldButton from "../components/HoldButton";
import CursorGrid from "../components/CursorGrid";
import SpecularFrame from "../components/SpecularFrame";
import "./LoginPage.css";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<"login" | "register">(
    searchParams.get("mode") === "register" ? "register" : "login",
  );
  const [form, setForm] = useState({ username: "", password: "", displayName: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordStatus, setPasswordStatus] = useState<"idle" | "error">("idle");
  const formRef = useRef<HTMLFormElement>(null);
  const submitting = useRef(false);

  const submit = async (element: HTMLFormElement) => {
    if (submitting.current) return;
    // Read native fields too: some password managers fill without input events.
    const fields = new FormData(element);
    const username = String(fields.get("username") ?? form.username);
    const password = String(fields.get("password") ?? form.password);
    setForm((current) => ({ ...current, username, password }));
    if (!/^\d{8}$/.test(password)) {
      setPasswordStatus("error");
      setError("请输入完整的 8 位数字密码。");
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(username, password);
      else await register(username, password, form.displayName || username);
      navigate("/", { replace: true });
    } catch (err) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } })?.response;
      const detail = response?.data?.detail;
      const serviceUnavailable = !response || (response.status ?? 0) >= 500;
      setError(serviceUnavailable
        ? "暂时无法连接登录服务，请稍后重试。"
        : typeof detail === "string" ? detail : "登录失败，请检查账号信息。");
      // A service outage should not mark the password invalid or clear it.
      if (!serviceUnavailable && response?.status === 401) setPasswordStatus("error");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <WhaleLoginBackdrop />
      <div className="auth-card">
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
        <div className="auth-brand">
          <strong>稿流</strong>
          <span>AI 内容工作台</span>
        </div>
        <h1>{mode === "login" ? "登录" : "创建账号"}</h1>
        <p className="muted">使用用户名和 8 位数字密码继续创作、管理文章与素材。</p>

        <form
          ref={formRef}
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit(event.currentTarget);
          }}>
          <label>
            <span>用户名</span>
            <input
              id="auth-username"
              name="username"
              autoComplete="username"
              onChange={(e) => setForm((current) => ({ ...current, username: e.target.value }))}
              placeholder="username"
              required
              value={form.username}
            />
          </label>
          <label>
            <span>8 位数字密码</span>
            <CodeSlots
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              ariaLabel="8位数字密码"
              disabled={busy}
              gap={7}
              length={8}
              mask
              onChange={(password) => {
                setForm((current) => ({ ...current, password }));
                setPasswordStatus("idle");
                if (password) setError(null);
              }}
              slotSize={36}
              status={passwordStatus}
              value={form.password}
            />
          </label>
          {mode === "register" && (
            <label>
              <span>显示名称</span>
              <input
                onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                placeholder="可选"
                value={form.displayName}
              />
            </label>
          )}
          {mode === "login" ? (
            <div className="auth-login-action">
              <HoldButton
                className="auth-login-button"
                backgroundColor="#16375d"
                fillColor="#368fe2"
                textColor="#e2f0ff"
                fillTextColor="#ffffff"
                icon={<LogIn size={17} aria-hidden="true" />}
                doneIcon={busy ? <LoaderCircle className="auth-login-spinner" size={17} aria-hidden="true" /> : <Check size={17} aria-hidden="true" />}
                doneLabel={busy ? "正在登录…" : "正在连接…"}
                holdTime={500}
                releaseTime={240}
                resetAfter={0}
                pressScale={0.99}
                radius={11}
                waveAmplitude={4}
                size="lg"
                busy={busy}
                disabled={busy}
                onBeforeHold={() => !submitting.current && (formRef.current?.reportValidity() ?? false)}
                onHold={() => formRef.current?.requestSubmit()}
              >
                长按登录
              </HoldButton>
              <p className="auth-login-hint">按住 0.5 秒登录，松开取消 · 输入后也可按 Enter</p>
              <button type="submit" hidden tabIndex={-1} aria-hidden="true" style={{ display: "none" }} />
            </div>
          ) : (
            <button className="button button--primary auth-register-button" disabled={busy} type="submit">
              {busy ? <LoaderCircle className="auth-login-spinner" size={16} /> : <UserPlus size={16} />}
              {busy ? "处理中…" : "注册"}
            </button>
          )}
        </form>

        {error && <div className="auth-error" role="alert">{error}</div>}

        <button
          className="auth-switch"
          disabled={busy}
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
            setPasswordStatus("idle");
          }}
          type="button">
          {mode === "login" ? "还没有账号？注册" : "已有账号？登录"}
        </button>
        <button
          className="auth-switch"
          onClick={() => navigate("/landing")}
          type="button"
        >
          了解稿流 →
        </button>
      </div>
    </main>
  );
}
