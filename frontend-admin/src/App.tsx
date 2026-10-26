import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, LoaderCircle, LogOut, Plus, RefreshCw, Star, Trash2, XCircle } from "lucide-react";
import { api } from "./api";
import AdminLoginPage from "./AdminLoginPage";
import { AdminAuthProvider, useAdminAuth } from "./AuthContext";

interface ModelStatus {
  baseUrl: string;
  model: string;
  keyConfigured: boolean;
  keySource: "db" | "env" | "none";
  keyHint: string;
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
  keySource: "db" | "env" | "none";
  keyHint: string;
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

interface ImageStatus {
  baseUrl: string;
  model: string;
  apiKeyEnv: string;
  keyConfigured: boolean;
  keySource: "db" | "env" | "none";
  keyHint: string;
  timeoutSeconds: number;
  source: "db" | "env" | "fallback";
}

const emptyImageForm = {
  baseUrl: "",
  modelId: "",
  apiKeyEnv: "IMAGE_API_KEY",
  timeoutSeconds: 180,
};

function AiConfigPage() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [profiles, setProfiles] = useState<ProfileOut[]>([]);
  const [image, setImage] = useState<ImageStatus | null>(null);
  const [imageForm, setImageForm] = useState(emptyImageForm);
  const [showImageForm, setShowImageForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [llmKeyInput, setLlmKeyInput] = useState("");
  const [imageKeyInput, setImageKeyInput] = useState("");
  const [profileKeyInputs, setProfileKeyInputs] = useState<Record<string, string>>({});
  const { logout, user } = useAdminAuth();

  const load = useCallback(async () => {
    setError(null);
    try {
      const [statusRes, profilesRes, imageRes] = await Promise.all([
        api.get<ModelStatus>("/settings/model"),
        api.get<{ profiles: ProfileOut[] }>("/settings/profiles"),
        api.get<ImageStatus>("/settings/image"),
      ]);
      setStatus(statusRes.data);
      setProfiles(profilesRes.data.profiles);
      setImage(imageRes.data);
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

  const openImageForm = () => {
    if (image && image.source === "db") {
      setImageForm({
        baseUrl: image.baseUrl,
        modelId: image.model,
        apiKeyEnv: image.apiKeyEnv,
        timeoutSeconds: image.timeoutSeconds,
      });
    } else {
      setImageForm(emptyImageForm);
    }
    setShowImageForm(true);
  };

  const saveImage = async () => {
    if (!imageForm.baseUrl.trim() || !imageForm.modelId.trim()) {
      setError("生图 API Base URL / 模型 ID 必填。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.put<ImageStatus>("/settings/image", imageForm);
      setShowImageForm(false);
      await load();
      setMessage("生图配置已保存。");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "生图配置保存失败。");
    } finally {
      setBusy(false);
    }
  };

  const resetImage = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.delete<ImageStatus>("/settings/image");
      setShowImageForm(false);
      await load();
      setMessage("已恢复环境变量默认配置。");
    } catch {
      setError("重置失败。");
    } finally {
      setBusy(false);
    }
  };

  const testImage = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const res = await api.post<{ latencyMs: number; model: string }>("/settings/image/test");
      setMessage(`生图连通正常：${res.data.model} · ${res.data.latencyMs}ms`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "生图连通测试失败。");
    } finally {
      setBusy(false);
    }
  };

  const saveLlmKey = async () => {
    const value = llmKeyInput.trim();
    if (value.length < 4) {
      setError("密钥长度至少 4 位。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.put("/settings/llm/key", { apiKey: value });
      setLlmKeyInput("");
      await load();
      setMessage("LLM 密钥已加密入库。");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "密钥保存失败。");
    } finally {
      setBusy(false);
    }
  };

  const removeLlmKey = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.delete("/settings/llm/key");
      await load();
      setMessage("LLM 密钥已删除，回退环境变量。");
    } catch {
      setError("密钥删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const saveImageKey = async () => {
    const value = imageKeyInput.trim();
    if (value.length < 4) {
      setError("密钥长度至少 4 位。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.put("/settings/image/key", { apiKey: value });
      setImageKeyInput("");
      await load();
      setMessage("生图密钥已加密入库。");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "密钥保存失败。");
    } finally {
      setBusy(false);
    }
  };

  const removeImageKey = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.delete("/settings/image/key");
      await load();
      setMessage("生图密钥已删除，回退环境变量。");
    } catch {
      setError("密钥删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const saveProfileKey = async (id: string) => {
    const value = (profileKeyInputs[id] ?? "").trim();
    if (value.length < 4) {
      setError("密钥长度至少 4 位。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.put(`/settings/profiles/${id}/key`, { apiKey: value });
      setProfileKeyInputs({ ...profileKeyInputs, [id]: "" });
      await load();
      setMessage("档案密钥已加密入库。");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "密钥保存失败。");
    } finally {
      setBusy(false);
    }
  };

  const removeProfileKey = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/settings/profiles/${id}/key`);
      await load();
      setMessage("档案密钥已删除，回退环境变量。");
    } catch {
      setError("密钥删除失败。");
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
          <>
          <div className="config-grid">
            <div><small>API Base URL</small><strong>{status.baseUrl}</strong></div>
            <div><small>模型</small><strong>{status.model}</strong></div>
            <div><small>密钥变量</small><strong>{status.apiKeyEnv}</strong></div>
            <div><small>密钥状态</small><strong>{status.keyConfigured ? `已配置（${status.keySource === "db" ? "数据库加密" : "环境变量"}）` : "未配置"}</strong></div>
            <div><small>生效档案</small><strong>{status.profileName ?? "全局环境变量"}</strong></div>
            <div><small>超时</small><strong>{status.timeoutSeconds}s</strong></div>
          </div>
          <div className="admin-form" style={{ marginTop: 12 }}>
            <input autoComplete="new-password" onChange={(e) => setLlmKeyInput(e.target.value)} placeholder="录入全局 LLM 密钥（加密入库，不回显）" type="password" value={llmKeyInput} />
            <button className="primary" disabled={busy} onClick={() => void saveLlmKey()} type="button">保存密钥</button>
            {status.keySource === "db" && (
              <button className="quiet" disabled={busy} onClick={() => void removeLlmKey()} type="button">删除密钥</button>
            )}
          </div>
          {status.keyHint && (
            <p className="muted">当前密钥 {status.keyHint}（来源：{status.keySource === "db" ? "数据库加密存储" : "环境变量"}）</p>
          )}
          </>
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
                <small>{profile.baseUrl} · {profile.modelId} · {profile.apiKeyEnv} · {profile.keyConfigured ? `Key 已配置（${profile.keySource === "db" ? "数据库" : "环境变量"}）${profile.keyHint}` : "Key 未配置"} · {profile.timeoutSeconds}s</small>
              </div>
              <div className="admin-form" style={{ marginTop: 8 }}>
                <input autoComplete="new-password" onChange={(e) => setProfileKeyInputs({ ...profileKeyInputs, [profile.id]: e.target.value })} placeholder="录入该档案密钥（加密入库，不回显）" type="password" value={profileKeyInputs[profile.id] ?? ""} />
                <button className="quiet" disabled={busy} onClick={() => void saveProfileKey(profile.id)} type="button">存密钥</button>
                {profile.keySource === "db" && (
                  <button className="quiet" disabled={busy} onClick={() => void removeProfileKey(profile.id)} type="button">删密钥</button>
                )}
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
        <div className="section-head">
          <h2>生图模型配置</h2>
          <div>
            <button className="quiet" onClick={() => void load()} type="button"><RefreshCw size={14} /> 刷新</button>
            <button className="primary" disabled={busy} onClick={() => void testImage()} type="button">
              {busy ? <LoaderCircle className="spin" size={14} /> : <CheckCircle2 size={14} />} 测试生图
            </button>
          </div>
        </div>
        {image ? (
          <>
            <div className="config-grid">
              <div><small>API Base URL</small><strong>{image.baseUrl}</strong></div>
              <div><small>模型</small><strong>{image.model}</strong></div>
              <div><small>密钥变量</small><strong>{image.apiKeyEnv}</strong></div>
              <div><small>密钥状态</small><strong>{image.keyConfigured ? `已配置（${image.keySource === "db" ? "数据库加密" : "环境变量"}）` : "未配置"}</strong></div>
              <div><small>配置来源</small><strong>{image.source === "db" ? "管理端配置" : image.source === "env" ? "环境变量" : "回退文本模型"}</strong></div>
              <div><small>超时</small><strong>{image.timeoutSeconds}s</strong></div>
            </div>
            <div className="admin-form" style={{ marginTop: 12 }}>
              <input autoComplete="new-password" onChange={(e) => setImageKeyInput(e.target.value)} placeholder="录入生图密钥（加密入库，不回显；留空表示沿用文本模型密钥）" type="password" value={imageKeyInput} />
              <button className="primary" disabled={busy} onClick={() => void saveImageKey()} type="button">保存密钥</button>
              {image.keySource === "db" && (
                <button className="quiet" disabled={busy} onClick={() => void removeImageKey()} type="button">删除密钥</button>
              )}
            </div>
            {image.keyHint && (
              <p className="muted">当前生图密钥 {image.keyHint}（来源：{image.keySource === "db" ? "数据库加密存储" : "环境变量"}）</p>
            )}
            <div className="section-head" style={{ marginTop: 12 }}>
              <span className="muted">密钥支持两种方式：数据库加密存储（推荐）或后端环境变量；均不回显明文。</span>
              <div>
                <button className="quiet" onClick={openImageForm} type="button">编辑配置</button>
                {image.source === "db" && (
                  <button className="quiet" disabled={busy} onClick={() => void resetImage()} type="button">恢复环境变量默认</button>
                )}
              </div>
            </div>
            {showImageForm && (
              <form
                className="admin-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void saveImage();
                }}>
                <input onChange={(e) => setImageForm({ ...imageForm, baseUrl: e.target.value })} placeholder="生图 API Base URL，例如 https://api.openai.com/v1" required value={imageForm.baseUrl} />
                <input onChange={(e) => setImageForm({ ...imageForm, modelId: e.target.value })} placeholder="生图模型 ID，例如 gpt-image-1" required value={imageForm.modelId} />
                <input onChange={(e) => setImageForm({ ...imageForm, apiKeyEnv: e.target.value })} placeholder="密钥环境变量名，默认 IMAGE_API_KEY" value={imageForm.apiKeyEnv} />
                <input min={1} onChange={(e) => setImageForm({ ...imageForm, timeoutSeconds: Number(e.target.value) || 180 })} placeholder="超时秒数" type="number" value={imageForm.timeoutSeconds} />
                <button className="primary" disabled={busy} type="submit">保存生图配置</button>
              </form>
            )}
          </>
        ) : (
          <p className="muted">加载中...</p>
        )}
      </section>

      <section className="admin-card">
        <h2>密钥安全约定</h2>
        <p className="muted">
          企业级密钥约定（2026-10-26 起）：API Key 密文经 Fernet 信封加密存入后端数据库（app_secrets），主密钥通过 SECRET_ENCRYPTION_KEY 环境变量注入、不进仓库；环境变量密钥保留为回退/开发路径。明文不回显到浏览器，不进日志。
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





