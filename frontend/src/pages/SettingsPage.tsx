import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, KeyRound, ListChecks, LoaderCircle, Monitor, Moon, Plus, RefreshCw, Star, Sun, Trash2, XCircle } from "lucide-react";
import { useThemeSetting, type ThemeSetting } from "../lib/theme";
import { api } from "../api/client";

// 设置页：蓝本 SettingsPage + model-profile 管理的 Web 版。
// 密钥永远只走服务端环境变量（与蓝本 secret-provider 同一安全边界）：
// 档案只保存环境变量名（apiKeyEnv），浏览器永远拿不到密钥本体。

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
  createdAt: string | null;
}

const emptyForm = {
  name: "",
  baseUrl: "",
  modelId: "",
  apiKeyEnv: "LLM_API_KEY",
  timeoutSeconds: 120,
};

export default function SettingsPage() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [profiles, setProfiles] = useState<ProfileOut[]>([]);
  const [form, setForm] = useState(emptyForm);
  const { setting: themeSetting, setSetting: setThemeSetting } = useThemeSetting();
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [models, setModels] = useState<string[] | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageForm, setImageForm] = useState({
    baseUrl: "",
    modelId: "gpt-image-1",
    apiKeyEnv: "IMAGE_API_KEY",
    timeoutSeconds: 180,
  });
  const [imageSaved, setImageSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const [statusRes, profilesRes] = await Promise.all([
        api.get<ModelStatus>("/settings/model"),
        api.get<{ profiles: ProfileOut[] }>("/settings/profiles"),
      ]);
      setStatus(statusRes.data);
      setProfiles(profilesRes.data.profiles);
    } catch {
      setError("无法读取模型配置。");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const res = await api.post<{ latencyMs: number; model: string; reply: string; profileName: string | null }>(
        "/settings/model/test",
      );
      setTestResult(
        `连通正常 · ${res.data.profileName ? `${res.data.profileName} · ` : ""}${res.data.model} · ${res.data.latencyMs}ms · 回复：${res.data.reply}`,
      );
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setTestResult(null);
      setError(typeof detail === "string" ? detail : "测试失败。");
    } finally {
      setTesting(false);
    }
  };

  const discover = async () => {
    setLoadingModels(true);
    setError(null);
    try {
      const res = await api.get<{ models: string[] }>("/settings/models");
      setModels(res.data.models);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "模型列表拉取失败。");
    } finally {
      setLoadingModels(false);
    }
  };

  const createProfile = async () => {
    if (!form.name.trim() || !form.baseUrl.trim() || !form.modelId.trim()) {
      setError("档案名称 / Base URL / 模型 ID 为必填项。");
      return;
    }
    setError(null);
    try {
      await api.post("/settings/profiles", {
        name: form.name.trim(),
        baseUrl: form.baseUrl.trim(),
        modelId: form.modelId.trim(),
        apiKeyEnv: form.apiKeyEnv.trim() || "LLM_API_KEY",
        timeoutSeconds: form.timeoutSeconds,
        isDefault: profiles.length === 0,
      });
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "创建档案失败。");
    }
  };

  const activateProfile = async (id: string) => {
    setError(null);
    try {
      await api.post(`/settings/profiles/${id}/activate`);
      await load();
    } catch {
      setError("激活档案失败。");
    }
  };

  const deleteProfile = async (id: string) => {
    setError(null);
    try {
      await api.delete(`/settings/profiles/${id}`);
      await load();
    } catch {
      setError("删除档案失败。");
    }
  };

  const saveImageConfig = () => {
    if (!imageForm.modelId.trim()) {
      setError("生图模型 ID 不能为空。");
      return;
    }
    localStorage.setItem("opw_image_config", JSON.stringify(imageForm));
    setImageSaved(true);
    setError(null);
  };

  return (
    <div className="settings-page" style={{ padding: "20px 24px", display: "grid", gap: 16, maxWidth: 760 }}>
      <div>
        <p className="page-kicker">设置</p>
        <h1>设置</h1>
      </div>

      <div className="panel" style={{ display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0 }}>生图模型</h2>
        <p className="muted" style={{ fontSize: 12 }}>
          生图与文本模型独立配置；服务端优先读取 IMAGE_* 环境变量，未配置时回退 LLM_*。
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <input
            onChange={(event) => setImageForm({ ...imageForm, baseUrl: event.target.value })}
            placeholder="IMAGE_BASE_URL（留空则回退 LLM Base URL）"
            value={imageForm.baseUrl}
          />
          <input
            onChange={(event) => setImageForm({ ...imageForm, modelId: event.target.value })}
            placeholder="IMAGE_MODEL，例如 gpt-image-1"
            value={imageForm.modelId}
          />
          <input
            onChange={(event) => setImageForm({ ...imageForm, apiKeyEnv: event.target.value })}
            placeholder="IMAGE_API_KEY"
            value={imageForm.apiKeyEnv}
          />
          <input
            onChange={(event) => setImageForm({
              ...imageForm,
              timeoutSeconds: Number(event.target.value) || 180,
            })}
            type="number"
            value={imageForm.timeoutSeconds}
          />
        </div>
        <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
          <button className="button button--primary" onClick={saveImageConfig} type="button">
            保存生图偏好
          </button>
          {imageSaved && <span style={{ color: "var(--success)", fontSize: 13 }}>已保存到本地界面</span>}
        </div>
        <small className="muted">
          密钥本体仍只写入 .env：IMAGE_API_KEY / IMAGE_BASE_URL / IMAGE_MODEL / IMAGE_TIMEOUT_SECONDS。
        </small>
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

      {status && (
        <div className="panel" style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {status.keyConfigured ? (
              <CheckCircle2 size={16} color="var(--success)" />
            ) : (
              <XCircle size={16} color="var(--danger)" />
            )}
            <strong>
              {status.keyConfigured
                ? `API Key 已配置（来源：${status.profileName ?? "全局环境变量"}，仅服务端持有）`
                : "未配置 LLM_API_KEY"}
            </strong>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 16px", fontSize: 13 }}>
            <span className="muted">Base URL</span><span>{status.baseUrl}</span>
            <span className="muted">模型</span><span>{status.model}</span>
            <span className="muted">密钥变量</span><span>{status.apiKeyEnv}</span>
            <span className="muted">超时</span><span>{status.timeoutSeconds}s</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="button button--primary" disabled={testing} onClick={() => void runTest()} type="button">
              {testing ? <LoaderCircle className="spin" size={15} /> : <KeyRound size={15} />}
              {testing ? "测试中……" : "测试连通性"}
            </button>
            <button className="button button--quiet" disabled={loadingModels} onClick={() => void discover()} type="button">
              {loadingModels ? <LoaderCircle className="spin" size={15} /> : <ListChecks size={15} />}
              {loadingModels ? "拉取中……" : "发现可用模型"}
            </button>
            <button className="icon-button" onClick={() => void load()} title="刷新" type="button">
              <RefreshCw size={15} />
            </button>
          </div>
          {testResult && (
            <p style={{ color: "var(--success)", fontSize: 13 }}>{testResult}</p>
          )}
          {models && (
            <details>
              <summary style={{ cursor: "pointer", fontSize: 13 }}>
                可用模型（{models.length}）
              </summary>
              <ul style={{ fontSize: 12, lineHeight: 1.8, margin: "8px 0 0", paddingLeft: 18 }}>
                {models.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      <div className="panel" style={{ display: "grid", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>API 接入（模型档案）</h2>
          <button
            className="button button--quiet"
            onClick={() => setShowForm((v) => !v)}
            type="button"
          >
            <Plus size={15} />
            {showForm ? "收起" : "新建档案"}
          </button>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          蓝本 TextModelProfile 的 Web 版：每个档案绑定一个服务端密钥环境变量名，
          密钥本体永不入库、不下发浏览器。激活的档案覆盖全局 LLM_* 配置。
        </p>
        {showForm && (
          <div style={{ display: "grid", gap: 8, border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <input
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="档案名称（必填）例如：DeepSeek 官方"
                value={form.name}
              />
              <input
                onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
                placeholder="Base URL（必填）例如：https://api.deepseek.com/v1"
                value={form.baseUrl}
              />
              <input
                onChange={(e) => setForm({ ...form, modelId: e.target.value })}
                placeholder="模型 ID（必填）例如：deepseek-chat"
                value={form.modelId}
              />
              <input
                onChange={(e) => setForm({ ...form, apiKeyEnv: e.target.value })}
                placeholder="密钥环境变量名，例如 DEEPSEEK_API_KEY"
                value={form.apiKeyEnv}
              />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                onChange={(e) => setForm({ ...form, timeoutSeconds: Number(e.target.value) || 120 })}
                style={{ width: 90 }}
                type="number"
                value={form.timeoutSeconds}
              />
              <span className="muted" style={{ fontSize: 12 }}>超时秒数</span>
              <button className="button button--primary" onClick={() => void createProfile()} type="button">
                保存档案
              </button>
            </div>
            <small className="muted">
              密钥本体请配置在 open-publisher-web/.env 或宿主环境变量中，变量名与上面填写的一致。
            </small>
          </div>
        )}
        {profiles.length === 0 && !showForm && (
          <p className="muted" style={{ fontSize: 12 }}>
            还没有档案：当前使用全局 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。
          </p>
        )}
        <div style={{ display: "grid", gap: 8 }}>
          {profiles.map((profile) => (
            <div
              key={profile.id}
              style={{
                alignItems: "center",
                border: `1px solid ${profile.isDefault ? "var(--accent)" : "var(--border)"}`,
                borderRadius: 8,
                display: "grid",
                fontSize: 13,
                gap: 4,
                gridTemplateColumns: "1fr auto",
                padding: "10px 12px",
              }}
            >
              <div>
                <strong>
                  {profile.isDefault && <Star color="var(--accent)" size={13} />}{""}
                  {profile.name}
                  {status?.profileId === profile.id && (
                    <span className="muted" style={{ fontSize: 11 }}>（当前生效）</span>
                  )}
                </strong>
                <div className="muted" style={{ fontSize: 12 }}>
                  {profile.baseUrl} · {profile.modelId} · 密钥变量 {profile.apiKeyEnv}
                  {profile.keyConfigured ? "（已配置）" : "（未配置）"} · {profile.timeoutSeconds}s
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {!profile.isDefault && (
                  <button
                    className="button button--quiet"
                    onClick={() => void activateProfile(profile.id)}
                    type="button"
                  >
                    激活
                  </button>
                )}
                <button
                  aria-label={`删除 ${profile.name}`}
                  className="icon-button"
                  onClick={() => void deleteProfile(profile.id)}
                  title="删除档案"
                  type="button"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="workflow-task__failure" role="alert">
          <p>{error}</p>
        </div>
      )}

      <div className="panel">
        <h2>如何配置 Key</h2>
        <p className="muted">
          出于安全考虑（浏览器永远不接触密钥），密钥通过服务端环境变量配置：
        </p>
        <pre className="code-block">{`# open-publisher-web/.env
LLM_API_KEY=你的key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
# 多档案时，为每个档案准备独立变量，例如
DEEPSEEK_API_KEY=另一把key`}</pre>
        <p className="muted">修改后重启生效：docker compose up -d --build backend</p>
      </div>

      <div className="panel">
        <h2>安全边界（继承蓝本）</h2>
        <p className="muted">
          密钥只存在于服务端进程；前端所有 LLM / 图片调用都经过后端代理。
          蓝本的 secret-lease 机制在 Web 版等价为环境变量注入；模型档案只保存变量名。
        </p>
        <h3 style={{ margin: "8px 0 0" }}>预留：设置页直接填写密钥</h3>
        <p className="muted" style={{ fontSize: 12 }}>
          计划中的能力：在设置页提交密钥 → 后端校验后加密落盘（或注入运行时环境），
          前端只回显「已配置」状态。当前版本请使用上面的环境变量方式；
          上方「API 接入」板块即为未来的密钥填写入口预留。
        </p>
      </div>
    </div>
  );
}
