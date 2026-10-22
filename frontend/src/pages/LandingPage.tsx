import { useNavigate } from "react-router-dom";
import { ArrowRight, Bot, FileText, ImageIcon, Lock, Send, Sparkles } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

// Landing Page：产品介绍 + CTA（PROJECT_PLAN 4.1 / 阶段 4）。
// 未登录访客与已登录用户都可访问；CTA 按登录态分流。

const FEATURES = [
  {
    icon: Bot,
    title: "多 Agent 创作引擎",
    description: "产品理解 → 受众分析 → 策略规划 → 写作 → 评分 → 优化 → 风险检查，一次输入成稿。",
  },
  {
    icon: FileText,
    title: "版本即权威",
    description: "每次生成与修改都是不可变版本，随时回溯、对比与恢复，不怕改丢。",
  },
  {
    icon: ImageIcon,
    title: "素材配图一体化",
    description: "素材库按语义自动匹配配图，缺图由生图模型补齐，正文自动插图。",
  },
  {
    icon: Send,
    title: "发布 Outbox",
    description: "审批绑定内容 → 幂等入队 → dry-run 演练，外部写入安全可控不重复。",
  },
  {
    icon: Lock,
    title: "密钥不出服务端",
    description: "API Key 只存在于服务端环境变量，模型接入由管理员统一配置，浏览器永不接触。",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const primaryCta = () => navigate(user ? "/" : "/login?mode=register");
  const primaryLabel = user ? "进入创作工作台" : "免费开始创作";

  return (
    <main className="landing-page">
      <header className="landing-nav">
        <div className="landing-nav__brand">
          <span className="brand-mark" aria-hidden="true">
            <img alt="" src="/gaoliu-mark.svg" />
          </span>
          <strong>稿流</strong>
        </div>
        <nav aria-label="Landing 导航" className="landing-nav__links">
          <button onClick={() => navigate(user ? "/" : "/login")} type="button">
            {user ? "打开工作台" : "登录"}
          </button>
          <button className="button button--primary" onClick={primaryCta} type="button">
            {primaryLabel}
            <ArrowRight aria-hidden="true" size={15} />
          </button>
        </nav>
      </header>

      <section className="landing-hero">
        <p className="page-kicker">Open Publisher Web</p>
        <h1>
          AI 长文创作
          <br />
          与多平台发布工作台
        </h1>
        <p className="landing-hero__sub">
          不是聊天工具，而是创作系统：多 Agent 理解你的产品、规划策略、生成评分、检查风险，
          版本全程可追溯，发布走幂等队列。
        </p>
        <div className="landing-hero__cta">
          <button className="button button--primary" onClick={primaryCta} type="button">
            <Sparkles aria-hidden="true" size={16} />
            {primaryLabel}
          </button>
          <button className="button button--quiet" onClick={() => navigate(user ? "/articles" : "/login")} type="button">
            查看我的文章
          </button>
        </div>
      </section>

      <section aria-label="核心能力" className="landing-features">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <article className="landing-feature" key={title}>
            <Icon aria-hidden="true" size={20} />
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
      </section>

      <section className="landing-flow" aria-label="创作流程">
        <h2>从一句话到可发布草稿</h2>
        <ol>
          <li>
            <strong>输入主题与资料</strong>
            <span>支持文件夹导入、参考文件、素材库图片与视觉输入。</span>
          </li>
          <li>
            <strong>Agent 工作流执行</strong>
            <span>8 节点流水线实时流式输出，过程与产物全程可见。</span>
          </li>
          <li>
            <strong>审阅与迭代</strong>
            <span>评分报告、风险提示、AI 一键优化，版本历史随时回退。</span>
          </li>
          <li>
            <strong>审批发布</strong>
            <span>多平台目标入队 dry-run，确认后进入发布队列。</span>
          </li>
        </ol>
        <button className="button button--primary" onClick={primaryCta} type="button">
          {primaryLabel}
          <ArrowRight aria-hidden="true" size={15} />
        </button>
      </section>

      <footer className="landing-footer">
        <span>稿流 · Open Publisher Web</span>
        <button onClick={() => navigate("/landing")} type="button">产品介绍</button>
      </footer>
    </main>
  );
}
