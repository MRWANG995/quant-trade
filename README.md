# Quant Trade — 日频多品类量化交易

面向国际市场（外汇、黄金、期货）的日频量化交易系统：每日 1–2 笔开仓，支持回测与模拟盘。

## 端口

| 服务 | 端口 |
|------|------|
| 后端 API | **9999** |
| 前端页面 | **9998** |
| PostgreSQL（Docker） | **5432** |

## 快速开始（本地 SQLite）

```bash
cp backend/.env.example backend/.env
```

### 后端

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 9999
```

### 同步真实行情

未配置 Key 时：外汇走 Frankfurter；黄金/期货优先 Stooq Key，否则 Yahoo（易限流）：

```bash
curl -X POST http://localhost:9999/api/data/bootstrap?force=true
```

### 前端

```bash
cd frontend && npm install && npm run dev
```

打开 http://localhost:9998

## 生产部署（Docker + PostgreSQL）

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env：STOOQ_API_KEY、SECRET_KEY 等
docker compose up -d --build
```

| 项 | 说明 |
|----|------|
| 数据库 | Postgres 16，自动 `alembic upgrade head` |
| 默认管理员 | `admin@example.com` / `changeme`（见 `docker-compose.yml`，务必修改） |
| 认证 | `REQUIRE_AUTH=true`，前端需登录 |
| API 文档 | http://localhost:9999/docs |

## 行情数据（无需 API Key 也能用）

| 品种 | 零 Key 时数据来源 |
|------|------------------|
| 外汇 EUR/GBP/JPY | **Frankfurter**（ECB 参考价，真实） |
| 黄金 / 期货 | 批量 **Yahoo**；仍失败则 **自动演示补全** |

全量灌库即可，不必配置 Stooq。若你能拿到 Key，可写入 `STOOQ_API_KEY` 获得更完整的黄金/期货真实 K 线（可选）。

`AUTO_DEMO_FALLBACK=true`（默认）：演示数据仅用于补全拉取失败的品种，不影响外汇真实价。

## 用户认证

| 变量 | 本地默认 | Docker 默认 |
|------|----------|-------------|
| `REQUIRE_AUTH` | `false` | `true` |
| `ALLOW_REGISTRATION` | `true` | `false` |
| `SECRET_KEY` | 需自行修改 | compose 中配置 |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 空 | 自动创建首个管理员 |

本地注册：`POST /api/auth/register` 或前端 http://localhost:9998/login

## 常用 API

| 接口 | 说明 |
|------|------|
| `GET /api/data/status` | K 线就绪状态 |
| `GET /api/data/stooq-test` | 验证 Stooq Key |
| `POST /api/data/bootstrap` | 全量灌库 |
| `POST /api/auth/login` | 登录获取 JWT |
| `POST /api/backtest` | 回测 |

完整文档：http://localhost:9999/docs
