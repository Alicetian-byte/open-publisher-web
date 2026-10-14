# Open Publisher Web

面向产品创作者、独立开发者和创业团队的 **AI 推文创作工作台**。

用户输入产品信息（名称、描述、官网/GitHub、目标用户、卖点），系统通过 LangGraph 多 Agent 工作流完成：

> 产品理解 → 受众分析 → 策略规划 → 推文生成 → 质量评分 → 自动优化 → 风险检查 → 平台格式化

最终输出可直接使用的多平台推文版本，全部生成与修改均保存为可追溯的版本记录。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2.x · Pydantic v2 |
| 数据库 | MySQL 8 |
| 缓存 / 队列 | Redis 7 |
| AI 工作流 | LangGraph（阶段 2 接入） |
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
- [ ] 阶段 2：LangGraph 8 节点工作流 + artifact 存储 + SSE 实时进度
- [ ] 阶段 3：前端工作台（创建项目 / 工作流可视化 / 候选推文 / 编辑器 / 版本历史）
- [ ] 阶段 4：发布计划队列 / 模板库 / 打磨
- [ ] 阶段 5：比赛材料（技术文档 / 演示视频 / 在线演示）
