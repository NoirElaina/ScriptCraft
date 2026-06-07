# ScriptCraft

ScriptCraft 是一个小说改编工作台。它把小说正文整理成章节，再通过 Agent 流程抽取故事卡片、生成 YAML 剧本，并提供图谱、编辑、导出和预演能力。

视频：
链接: https://pan.baidu.com/s/1RWKDmUDSIYfhp_MD_io-Tg?pwd=1111 提取码: 1111

## 现在能做什么

- 用户注册、登录、退出，登录态使用 HttpOnly Cookie JWT。
- 创建、打开、删除项目，项目名称可以在工作台内继续修改。
- 粘贴小说正文并解析章节，章节正文会保存到数据库。
- 后续追加章节时，只重新处理未分析或缺失结果的章节。
- 对每章进行 AI 章节分析，提取摘要、候选角色、地点、事件和可改编场景。
- 抽取故事元素卡片，沉淀角色、地点、事件、场景，并支持后续补充修正。
- 生成结构化 YAML 剧本，支持预览、编辑、保存版本和导出。
- YAML 校验失败时，可以调用 AI 修复当前剧本片段。
- 工作台中展示故事图谱，用关系视图查看角色、地点和事件连接。
- 剧本预演画布可以按场景播放角色对话和行动。
- Agent 执行画布会展示章节分析、元素抽取、剧本生成和修复过程中的实时消息。

## 项目流程

```text
小说正文
  -> 章节解析
  -> 章节分析
  -> 故事元素抽取
  -> YAML 剧本生成
  -> 编辑 / 修复 / 导出 / 预演
```

## 技术栈

- 前端：Vue 3、Vite、TypeScript、shadcn-vue、Tailwind CSS v4
- 交互与可视化：D3 Force、PixiJS、GSAP、yaml
- 后端：Python、uv、FastAPI、SQLAlchemy、PyMySQL
- Agent 与模型：LangGraph、LangChain OpenAI、LangChain Anthropic
- 认证：python-jose + HttpOnly Cookie JWT
- 数据库：MySQL

## 目录结构

```text
ScriptCraft/
  backend/                 后端服务
    auth/                  登录注册与 JWT Cookie
    chapter_analysis.py    章节分析 Agent
    database/              数据库连接与初始化 SQL
    llm/                   大模型配置与流式回调
    projects/              项目、章节、AI 任务接口
    script_generation/     剧本生成与 YAML 修复
    story_element_extraction/ 故事卡片抽取工具流
  frontend/                前端工作台
    src/api/               REST API 客户端
    src/components/        工作台组件
    src/views/             页面入口
  docs/                    文档
  config/                  本地配置目录
```

## 数据库

数据库表需要提前创建，SQL 文件在：

```text
backend/database/schema.sql
```

在 MySQL 中创建数据库后执行：

```sql
CREATE DATABASE IF NOT EXISTS scriptcraft DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE scriptcraft;
SOURCE backend/database/schema.sql;
```

## 配置

后端读取 `config/app.yml`。这个文件用于本地或服务器部署配置，不需要提交到仓库。

```yaml
database:
  driver: mysql+pymysql
  host: 127.0.0.1
  port: 3306
  database: scriptcraft
  username: root
  password: "password"
  charset: utf8mb4

llm:
  provider: openai
  openai:
    api_key: your-api-key
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3.7-max-preview

auth:
  jwt_secret: change-this-secret
  cookie_name: scriptcraft_token
  cookie_secure: false
  cookie_samesite: lax
  token_ttl_hours: 168
```

## 本地运行

后端：

```powershell
cd backend
uv sync
uv run python main.py
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。前端开发服务会把 `/api` 转发到 `http://127.0.0.1:8000`。

## 常用功能入口

- 顶部项目选择器：切换、创建、删除项目。
- 项目章节：查看章节、修改项目名称、打开小说输入、启动章节分析、抽取元素和生成剧本。
- 故事图谱：查看角色、地点、事件之间的关系。
- 剧本结果：预览、编辑、修复、保存、导出 YAML 剧本。
- 预演：打开剧本预演画布，按场景播放角色行动和对白。
- Agent 画布：查看当前 AI 任务的执行节点和实时消息。

## 文档

- [剧本 YAML Schema](docs/yaml-schema.md)
