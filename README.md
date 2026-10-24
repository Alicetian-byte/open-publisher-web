# Open Publisher Web

面向内容创作者与团队的 **AI 长文创作与发布工作台**（比赛项目，团队自研）。

把团队蓝本 open-publisher 的完整稿流整体迁移到 Web：文章创作（流式生成）、版本管理、AI 编辑助手、素材库与智能配图、模板库、发布 Outbox 与多用户数据归属，全部作为一等能力实现。

## 功能总览

- **文章创作**：填写创作要求后走创作 run（SSE 实时回显），可随时打断、失败保留上下文重试
- **文章工作台**：Markdown 编辑 / 分栏 / 预览三种视图，平台预览适配
- **AI 编辑助手**：选中改写、一键优化、快照撤销，所有 AI 写回可打断
- **配图中心**：
  - 配图栏自动识别正文图片与创作生成的 mermaid 图表（实时缩略图）
  - 上传素材 → 输入行号精确插入到正文对应行（不依赖光标）
  - 已插入配图 / AI 生成图表支持「编辑」菜单：删除 / 移动位置
  - AI 配图方案：自动匹配素材库图片，未命中位置调用生图模型生成并按锚点插入
- **版本管理**：每次保存生成新修订，可查看历史与一键恢复
- **素材库**：上传 / AI 生成图片，站内 `asset://` 引用
- **模板库 / 发布**：发布计划审批绑定、Outbox 幂等入队、dry-run 与远端核验
- **多用户**：注册登录（JWT），文章 / 项目 / 素材按用户隔离
- **管理后台**：独立 admin 前端，管理模型配置与公告

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2.x · Pydantic v2 |
| 数据库 | MySQL 8（Alembic 迁移） |
| 缓存 / 队列 | Redis 7 |
| AI 工作流 | Agent Run / RunJournal（SSE 流式） |
| 前端 | React 18 · TypeScript · Vite |
| 管理后台 | React + Vite（独立容器） |
| 部署 | Docker Compose |

## 项目结构

```
open-publisher-web/
├── backend/         # FastAPI 后端（API / ORM / Alembic 迁移 / 服务层）
├── frontend/        # React + Vite 用户端（创作 / 工作台 / 发布）
├── frontend-admin/  # 管理后台前端
└── docker-compose.yml
```

## 快速开始（Docker Compose）

```bash
cp .env.example .env   # 按需修改数据库密码、管理员账号与模型密钥
docker compose up -d --build
```

启动后：

- 用户端前端：http://localhost:5173
- 管理后台：http://localhost:5174
- 后端 API：http://localhost:8000/api
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

首次启动自动执行数据库迁移（`alembic upgrade head`），并按 `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` 初始化管理员账号。

> 安全约定：管理员密码等敏感配置只来自环境变量。代码内默认值仅为占位符，
> 未配置时启动会打警告，请务必在 `.env` 中设置后再对外提供服务。

### Mock LLM 模式（无真实 API Key）

没有配置真实模型 Key 时，可用内置 Mock 服务器跑通完整链路（演示 / E2E）：

```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d --build
```

Mock 服务器监听 http://localhost:8001，按节点返回脚本化响应，
创作工作流、SSE、版本保存、AI 优化端点均可完整验证。

## 本地开发（不用 Docker）

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env    # 填写数据库与管理员配置
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发模式下 Vite 会把 `/api` 代理到 http://localhost:8000（可用 `VITE_PROXY_TARGET` 覆盖）。

## 环境变量（脱敏约定）

所有秘密（数据库密码、JWT 密钥、LLM / 生图 API Key、管理员密码）一律通过 `.env` / 环境变量注入，参考 `.env.example` 中的占位符：

- 密钥永远不进入仓库、不出现在前端代码或日志中
- `.env` 已被 `.gitignore` 排除，仓库中只有 `.env.example` 占位模板
- 管理员账号密码通过 `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` 配置

## 路线图

- [x] 阶段 1：项目骨架（FastAPI + MySQL + Redis + React + Docker Compose + projects CRUD）
- [x] 阶段 2：多节点创作工作流 + artifact 存储 + SSE 实时进度
- [x] 阶段 3：前端工作台（创作 / 工作流可视化 / 编辑器 / 版本历史 / AI 优化）
- [x] 阶段 4：文章库、配图中心、模板库、发布队列、管理后台、多用户隔离
- [ ] 阶段 5：比赛材料（技术文档 / 演示视频 / 在线演示）
