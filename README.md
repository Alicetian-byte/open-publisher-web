# Open Publisher Web

面向内容创作者与团队的 **AI 长文创作与发布工作台**。

项目目标是把团队蓝本 open-publisher 的完整稿流整体迁移到 Web：文章创作、流式写作、版本管理、AI 编辑助手、素材库与配图、模板库、发布 Outbox 与多用户数据归属都作为一等能力实现。

> 蓝本稿流的整体 Web 化：文章创作、版本管理、AI 编辑助手、素材配图、模板库、发布 Outbox、多用户 Web 端。

旧版 LangGraph 推文工作流仍作为实验模块保留，但不再是项目主方向。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2.x · Pydantic v2 |
| 数据库 | MySQL 8 |
| 缓存 / 队列 | Redis 7 |
| AI 工作流 | FastAPI Agent Run / RunJournal（蓝本 writer-service 思路） |
| 前端 | React 18 · TypeScript · Vite · Tailwind CSS |
| 部署 | Docker Compose |

## 项目结构

```
open-publisher-web/
├── backend/        # FastAPI 后端（API / ORM / Alembic 迁移）
├── frontend/       # React + Vite 前端
└── docker-compose.yml
```

## 快速开始（Docker Compose）

```bash
cp .env.example .env
docker compose up --build
```

启动后：

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000/api
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

首次启动会自动执行数据库迁移（alembic upgrade head）。

### Mock LLM 模式（无真实 API Key）

没有配置真实 LLM Key 时，可以用内置的 Mock 服务器跑通完整链路（演示 / E2E）：

```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d --build
```

Mock 服务器监听 http://localhost:8001，按 LangGraph 节点返回脚本化响应，
工作流、SSE、版本保存、AI 优化端点均可完整验证。
## 本地开发（不用 Docker）

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发模式下 Vite 会把 /api 代理到 http://localhost:8000。

## 环境变量

所有秘密（数据库密码、LLM API Key）一律通过 .env / 环境变量注入，参考 .env.example。
API Key 永远不进入仓库、不出现在前端代码中。

## 路线图

- [x] 阶段 1：项目骨架（FastAPI + MySQL + Redis + React + Docker Compose + projects CRUD）
- [x] 阶段 2：LangGraph 8 节点工作流 + artifact 存储 + SSE 实时进度
- [x] 阶段 3：前端工作台（创建项目 / 工作流可视化 / 候选推文 / 风险与评分报告 / 编辑器 / 版本历史 / AI 一键优化）
- [ ] 阶段 4：发布计划队列 / 模板库 / 打磨
- [ ] 阶段 5：比赛材料（技术文档 / 演示视频 / 在线演示）

