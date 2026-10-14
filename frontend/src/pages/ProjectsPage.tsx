import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Project } from "../types/project";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Project[]>("/projects");
      setProjects(res.data);
    } catch {
      setError("无法加载项目列表，请确认后端服务已启动。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post<Project>("/projects", {
        name: name.trim(),
        description: description.trim(),
      });
      setName("");
      setDescription("");
      await loadProjects();
    } catch {
      setError("创建项目失败，请稍后重试。");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/projects/${id}`);
      await loadProjects();
    } catch {
      setError("删除项目失败。");
    }
  };

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-base font-semibold">新建产品项目</h2>
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="name">
              产品名称 *
            </label>
            <input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="例如：Open Publisher Web"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" htmlFor="description">
              产品简介
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              placeholder="一句话介绍你的产品"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            创建项目
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-4 text-base font-semibold">项目列表</h2>
        {error && (
          <p className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}
        {loading ? (
          <p className="text-sm text-slate-500">加载中……</p>
        ) : projects.length === 0 ? (
          <p className="text-sm text-slate-500">还没有项目，先创建一个吧。</p>
        ) : (
          <ul className="space-y-3">
            {projects.map((p) => (
              <li
                key={p.id}
                className="flex items-start justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div>
                  <h3 className="font-medium">{p.name}</h3>
                  {p.description && (
                    <p className="mt-1 text-sm text-slate-600">{p.description}</p>
                  )}
                  <p className="mt-2 text-xs text-slate-400">
                    创建于 {new Date(p.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => void handleDelete(p.id)}
                  className="ml-4 shrink-0 rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
