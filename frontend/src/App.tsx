import { BrowserRouter, Route, Routes } from "react-router-dom";
import ProjectsPage from "./pages/ProjectsPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
            <h1 className="text-lg font-semibold">Open Publisher Web</h1>
            <span className="text-sm text-slate-500">AI 推文创作工作台</span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">
          <Routes>
            <Route path="/" element={<ProjectsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
