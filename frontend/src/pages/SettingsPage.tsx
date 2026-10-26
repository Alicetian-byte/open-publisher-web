import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useThemeSetting, type ThemeSetting } from "../lib/theme";
import { ARTICLE_WORKFLOW_NODES } from "../workflow/articleNodes";

interface Capabilities { contextWindow: number; maxTokens: number; vision: boolean; reasoning: boolean }
interface Profile { id: string; name: string; modelId: string; capabilities: Capabilities; keyConfigured: boolean }
interface Preferences { disabledNodeIds: string[]; webSearchMode: "auto" | "off"; profileId: string | null }
interface Integrations { trustedHosts: string[]; publishBridgeUrl: string; tavily?: {keyConfigured:boolean}; github?: {keyConfigured:boolean} }
export default function SettingsPage() {
  const { user, logout } = useAuth();
  const admin = user?.role === "admin";
  const { setting, setSetting } = useThemeSetting();
  const [tab, setTab] = useState("模型");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [prefs, setPrefs] = useState<Preferences>({disabledNodeIds:[], webSearchMode:"auto", profileId:null});
  const [integrations, setIntegrations] = useState<Integrations>({trustedHosts:[], publishBridgeUrl:""});
  const [keys, setKeys] = useState({tavily:"", github:""});
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>, success = "已保存") => { setBusy(true); setNotice(""); try { await fn(); setNotice(success); } catch { setNotice("操作失败，请检查输入与登录权限后重试。"); } finally { setBusy(false); } };
  useEffect(() => { void act(async () => {
    const [p, w] = await Promise.all([api.get<{profiles:Profile[]}>("/settings/profiles"), api.get<Preferences>("/settings/preferences")]);
    setProfiles(p.data.profiles); setPrefs(w.data);
    if (admin) setIntegrations((await api.get<Integrations>("/settings/integrations")).data);
  }, ""); }, [admin]);
  const exportData = async () => {
    const result = await api.get("/settings/data/export", {timeout:120000});
    const url = URL.createObjectURL(new Blob([JSON.stringify(result.data, null, 2)], {type:"application/json"}));
    const a = document.createElement("a"); a.href=url; a.download="稿流个人数据.json"; a.click(); URL.revokeObjectURL(url);
  };
  return <div className="settings-page" style={{padding:24, maxWidth:880, display:"grid", gap:16}}>
    <h1>设置</h1><nav className="mode-switch" aria-label="设置分类">{["模型","账号","写作","数据"].map(label => <button key={label} aria-pressed={tab===label} onClick={() => setTab(label)}>{label}</button>)}</nav>
    {notice && <p role="status">{notice}</p>}
    {tab === "模型" && <>
      <label className="field">默认写作模型<select value={prefs.profileId ?? ""} onChange={e => setPrefs({...prefs, profileId:e.target.value || null})}><option value="">平台默认</option>{profiles.map(p => <option key={p.id} value={p.id}>{p.name} · {p.modelId}</option>)}</select></label>
      <button className="button button--primary" disabled={busy} onClick={() => void act(() => api.put("/settings/preferences", prefs))}>保存模型选择</button>
      {profiles.map(p => <section className="panel" key={p.id} style={{padding:16, display:"grid", gap:10}}><strong>{p.name} · {p.keyConfigured ? "密钥已配置" : "密钥未配置"}</strong>
        <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>{(["contextWindow", "maxTokens"] as const).map(key => <label key={key}>{key === "contextWindow" ? "上下文窗口" : "最大输出 tokens"}<input type="number" disabled={!admin} value={p.capabilities[key]} onChange={e => setProfiles(ps => ps.map(item => item.id===p.id ? {...item, capabilities:{...item.capabilities, [key]:Number(e.target.value)}} : item))}/></label>)}
        {(["vision","reasoning"] as const).map(key => <label key={key}><input type="checkbox" disabled={!admin} checked={p.capabilities[key]} onChange={e => setProfiles(ps => ps.map(item => item.id===p.id ? {...item, capabilities:{...item.capabilities, [key]:e.target.checked}} : item))}/>{key === "vision" ? "图片理解" : "推理模型"}</label>)}</div>
        {admin && <button className="button button--quiet" disabled={busy} onClick={() => void act(() => api.patch(`/settings/profiles/${p.id}`, {capabilities:p.capabilities}))}>保存模型能力</button>}
      </section>)}<p className="muted">模型接入与密钥由管理员统一管理；此处选择仅影响你的写作。</p>
    </>}
    {tab === "账号" && <>
      <section className="panel" style={{padding:16}}><strong>{user?.displayName || user?.username}</strong><p>{admin ? "管理员" : "成员"}</p><button className="button button--quiet" onClick={() => void logout()}>退出登录</button></section>
      {admin ? <section className="panel" style={{padding:16,display:"grid",gap:12}}><h2>服务接入</h2>
        {(["tavily","github"] as const).map(kind => <div className="field" key={kind}><label>{kind === "tavily" ? "Tavily Key" : "GitHub Token"} · {integrations[kind]?.keyConfigured ? "已配置" : "未配置"}</label><input type="password" autoComplete="new-password" value={keys[kind]} onChange={e => setKeys({...keys,[kind]:e.target.value})}/><button className="button button--quiet" disabled={busy || !keys[kind].trim()} onClick={() => void act(async () => { await api.put(`/settings/integrations/${kind}/key`, {apiKey:keys[kind]}); setKeys(k => ({...k,[kind]:""})); setIntegrations(i => ({...i,[kind]:{keyConfigured:true}})); })}>加密保存</button></div>)}
        <label className="field">可信 Host（每行一个）<textarea value={integrations.trustedHosts.join("\n")} onChange={e => setIntegrations({...integrations,trustedHosts:e.target.value.split("\n")})}/></label>
        <label className="field">发布桥地址<input placeholder="https://bridge.example.com" value={integrations.publishBridgeUrl} onChange={e => setIntegrations({...integrations,publishBridgeUrl:e.target.value})}/></label>
        <p className="muted">保存接入配置不会投递文章。发布页显示当前可用通道。</p>
        <button className="button button--primary" disabled={busy} onClick={() => void act(() => api.put("/settings/integrations", {trustedHosts:integrations.trustedHosts,publishBridgeUrl:integrations.publishBridgeUrl}))}>保存接入设置</button>
      </section> : <p>服务接入由管理员配置。</p>}
    </>}
    {tab === "写作" && <section className="panel" style={{padding:16,display:"grid",gap:12}}>
      <h2>默认工作流</h2>{ARTICLE_WORKFLOW_NODES.map(node => <label key={node.id}><input type="checkbox" checked={!prefs.disabledNodeIds.includes(node.id)} onChange={e => setPrefs({...prefs,disabledNodeIds:e.target.checked ? prefs.disabledNodeIds.filter(id => id!==node.id) : [...prefs.disabledNodeIds,node.id]})}/>{node.label} <small className="muted">{node.description}</small></label>)}
      <label>联网检索<select value={prefs.webSearchMode} onChange={e => setPrefs({...prefs,webSearchMode:e.target.value as "auto"|"off"})}><option value="auto">自动</option><option value="off">关闭</option></select></label>
      <button className="button button--primary" disabled={busy} onClick={() => void act(() => api.put("/settings/preferences",prefs))}>保存写作偏好</button>
      <label>外观<select value={setting} onChange={e => setSetting(e.target.value as ThemeSetting)}><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label>
    </section>}
    {tab === "数据" && <section className="panel" style={{padding:16,display:"grid",gap:12}}><h2>安全与个人数据</h2><p>API 密钥在服务端加密保存，导出不包含密钥。个人文章、素材、模板和助手会话按账号隔离；历史共享内容按共享规则可读。</p><button className="button button--primary" disabled={busy} onClick={() => void act(exportData,"数据已导出")}>导出个人数据</button><button className="button button--quiet" disabled={busy} onClick={() => void act(async () => { const next = {disabledNodeIds:[],webSearchMode:"auto" as const,profileId:null}; await api.put("/settings/preferences", next); setPrefs(next); })}>重置个人写作偏好</button><a href="/articles">管理文章与历史版本</a><a href="/media">管理素材</a><a href="/templates">管理模板</a></section>}
  </div>;
}
