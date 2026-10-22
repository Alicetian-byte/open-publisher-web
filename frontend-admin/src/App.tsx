import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, LoaderCircle, LogOut, Plus, RefreshCw, Star, Trash2, XCircle } from "lucide-react";
import { api } from "./api";
import AdminLoginPage from "./AdminLoginPage";
import { AdminAuthProvider, useAdminAuth } from "./AuthContext";

interface ModelStatus {
  baseUrl: string;
  model: string;
  keyConfigured: boolean;
  timeoutSeconds: number;
  profileId: string | null;
  profileName: string | null;
  apiKeyEnv: string;
}

interface ProfileOut {
  id: string;
  name: string;
  provider: string;
  baseUrl: string;
  modelId: string;
  apiKeyEnv: string;
  keyConfigured: boolean;
  timeoutSeconds: number;
  isDefault: boolean;
}

const emptyForm = {
  name: "",
  provider: "custom",
  baseUrl: "",
  modelId: "",
  apiKeyEnv: "LLM_API_KEY",
  timeoutSeconds: 120,
};

function AiConfigPage() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [profiles, setProfiles] = useState<ProfileOut[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { logout, user } = useAdminAuth();

  const load = useCallback(async () => {
    setError(null);
    try {
      const [statusRes, profilesRes] = await Promise.all([
        api.get<ModelStatus>("/settings/model"),
        api.get<{ profiles: ProfileOut[] }>("/settings/profiles"),
      ]);
      setStatus(statusRes.data);
      setProfiles(profilesRes.data.profiles);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "无法读取 AI 配置。");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const createProfile = async () => {
    if (!form.name.trim() || !form.baseUrl.trim() || !form.modelId.trim()) {
      setError("档案名称 / API Base URL / 模型 ID 必填。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/settings/profiles", { ...form, isDefault: profiles.length === 0 });
      setForm(emptyForm);
      setShowForm(false);
      await load();
      setMessage("AI 档案已保存。");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "保存失败。");
    } finally {
      setBusy(false);
    }
  };

  const activate = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/settings/profiles/${id}/activate`);
      await load();
      setMessage("已切换生效档案。");
    } catch {
      setError("激活失败。");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/settings/profiles/${id}`);
      await load();
      setMessage("档案已删除。");
    } catch {
      setError("删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const res = await api.post<{ latencyMs: number; model: string; reply: string }>("/settings/model/test");
      setMessage(`连通正常：${res.data.model} · ${res.data.latencyMs}ms · ${res.data.reply}`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "连通测试失败。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin-shell">
      <header>
        <div>
          <small>管理控制台</small>
          <h1>AI 与 API 配置</h1>
        </div>
        <div className="admin-user">
          <span>{user?.displayName ?? user?.username}</span>
          <button className="quiet" onClick={() => void logout()} type="button">
            <LogOut size={14} /> 退出
          </button>
        </div>
      </header>

      <section className="admin-card">
        <div className="section-head">
          <h2>当前生效配置</h2>
          <div>
            <button className="quiet" onClick={() => void load()} type="button"><RefreshCw size={14} /> 刷新</button>
            <button className="primary" disabled={busy} onClick={() => void test()} type="button">
              {busy ? <LoaderCircle className="spin" size={14} /> : <CheckCircle2 size={14} />} 测试连通
            </button>
          </div>
        </div>
        {status ? (
          <div className="config-grid">
            <div><small>API Base URL</small><strong>{status.baseUrl}</strong></div>
            <div><small>模型</small><strong>{status.model}</strong></div>
            <div><small>密钥变量</small><strong>{status.apiKeyEnv}</strong></div>
            <div><small>密钥状态</small><strong>{status.keyConfigured ? "已配置" : "未配置"}</strong></div>
            <div><small>生效档案</small><strong>{status.profileName ?? "全局环境变量"}</strong></div>
            <div><small>超时</small><strong>{status.timeoutSeconds}s</strong></div>
          </div>
        ) : (
          <p className="muted">加载中...</p>
        )}
      </section>

      <section className="admin-card">
        <div className="section-head">
          <h2>模型档案</h2>
          <button className="primary" onClick={() => setShowForm(!showForm)} type="button">
            <Plus size={14} /> 新增配置
          </button>
        </div>

        {showForm && (
          <form
            className="admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              void createProfile();
            }}>
            <input onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="档案名称" required value={form.name} />
            <input onChange={(e) => setForm({ ...form, baseUrl: e.target.value })} placeholder="API Base URL，例如 https://api.openai.com/v1" required value={form.baseUrl} />
            <input onChange={(e) => setForm({ ...form, modelId: e.target.value })} placeholder="模型 ID，例如 gpt-4o-mini" required value={form.modelId} />
            <input onChange={(e) => setForm({ ...form, apiKeyEnv: e.target.value })} placeholder="密钥环境变量名" value={form.apiKeyEnv} />
            <input min={1} onChange={(e) => setForm({ ...form, timeoutSeconds: Number(e.target.value) || 120 })} placeholder="超时秒数" type="number" value={form.timeoutSeconds} />
            <button className="primary" disabled={busy} type="submit">保存配置</button>
          </form>
        )}

        <div className="profile-list">
          {profiles.map((profile) => (
            <div className={profile.isDefault ? "profile active" : "profile"} key={profile.id}>
              <div>
                <strong>{profile.isDefault && <Star color="#f59e0b" size={13} />} {profile.name}</strong>
                <small>{profile.baseUrl} · {profile.modelId} · {profile.apiKeyEnv} · {profile.keyConfigured ? "Key 已配置" : "Key 未配置"} · {profile.timeoutSeconds}s</small>
              </div>
              <div className="actions">
                {!profile.isDefault && <button className="quiet" disabled={busy} onClick={() => void activate(profile.id)} type="button">激活</button>}
                <button aria-label={`删除 ${profile.name}`} className="danger" disabled={busy} onClick={() => void remove(profile.id)} type="button"><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
          {profiles.length === 0 && <p className="muted">还没有模型档案。</p>}
        </div>
      </section>

      <section className="admin-card">
        <h2>密钥安全约定</h2>
        <p className="muted">
          遵循项目约束：API Key 本体只通过后端环境变量注入，不进入仓库，也不回显到浏览器。
          管理端填写 API 地址、模型、超时和密钥环境变量名；服务端会在运行时读取该变量。
        </p>
      </section>

      {message && <div className="success">{message}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  );
}

function AdminGate() {
  const { user, loading } = useAdminAuth();
  if (loading) {
    return (
      <main className="admin-login">
        <div className="admin-card">正在恢复登录状态...</div>
      </main>
    );
  }
  if (!user) return <AdminLoginPage />;
  if (user.role !== "admin") {
    return (
      <main className="admin-login">
        <div className="admin-card"><XCircle size={18} /> 当前账号没有管理员权限。</div>
      </main>
    );
  }
  return <AiConfigPage />;
}



export default function AdminApp() {
  return (
    <AdminAuthProvider>
      <AdminGate />
    </AdminAuthProvider>
  );
}
