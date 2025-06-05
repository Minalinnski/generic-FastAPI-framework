# FastAPI DDD Framework

一个现代化、可扩展的FastAPI框架，遵循领域驱动设计（DDD）原则，内置完善的任务管理系统和缓存机制。

## ✨ 主要特性

### 🏗️ 架构设计
- **DDD分层架构**: API层、应用层、领域层、基础设施层清晰分离
- **现代化依赖管理**: 使用pyproject.toml，支持Python 3.11+
- **配置分离**: 核心配置与业务配置分离，支持环境变量覆盖

### 🚀 任务系统
- **优先级队列**: 支持任务优先级调度
- **并发控制**: 可配置的工作线程数量
- **状态追踪**: 完整的任务生命周期管理
- **超时处理**: 任务超时自动处理和重试
- **LRU缓存**: 任务结果智能缓存，自动清理

### 🛠️ 基础设施
- **限流控制**: 多种限流策略（滑动窗口、令牌桶）
- **重试机制**: 指数退避、断路器模式
- **缓存装饰器**: 自动缓存函数结果
- **结构化日志**: 基于structlog的现代日志系统

### 📊 可观测性
- **健康检查**: 多层级健康状态监控
- **性能监控**: 请求追踪、任务统计
- **错误处理**: 统一异常处理和错误响应

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Redis (可选，用于分布式缓存)

### 安装和运行

1. **克隆项目**
```bash
git clone <repository-url>
cd fastapi-ddd-framework
```

2. **环境配置**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vim .env
```

3. **启动服务**
```bash
# 开发模式
chmod +x run.sh
./run.sh

# 或使用Make命令
make dev

# 生产模式
make prod
```

4. **Docker方式**
```bash
# 构建并启动
make docker-up

# 查看日志
make docker-logs
```

### 访问服务
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health
- 任务管理: http://localhost:8000/api/v1/tasks

## 📖 使用指南

### 任务系统使用

#### 1. 注册自定义任务
```python
# app/application/services/my_service.py
from app.infrastructure.tasks.task_registry import register_service_as_task

@register_service_as_task("my_custom_task")
async def my_business_logic(data: dict) -> dict:
    # 你的业务逻辑
    result = await process_data(data)
    return {"processed": True, "result": result}
```

#### 2. 提交任务
```python
# 通过API提交
POST /api/v1/tasks/submit
{
    "task_name": "my_custom_task",
    "task_type": "async",
    "params": {"input": "data"},
    "priority": 1,
    "timeout": 300
}
```

#### 3. 查询任务状态
```python
# 获取任务状态
GET /api/v1/tasks/{task_id}/status

# 获取任务列表
GET /api/v1/tasks?limit=50&offset=0

# 获取任务历史
GET /api/v1/tasks/history?status=success&limit=100
```

### 缓存使用

#### 1. 装饰器缓存
```python
from app.infrastructure.decorators.cache import cache

@cache(ttl=3600, key_prefix="user:")
async def get_user_data(user_id: str):
    # 这个函数的结果会被缓存1小时
    return await fetch_user_from_db(user_id)
```

#### 2. 限流装饰器
```python
from app.infrastructure.decorators.rate_limit import api_rate_limit

@api_rate_limit(requests_per_minute=30)
async def sensitive_operation():
    # 这个接口每分钟最多调用30次
    pass
```

#### 3. 重试装饰器
```python
from app.infrastructure.decorators.retry import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
async def unreliable_operation():
    # 失败时会自动重试，使用指数退避
    pass
```

### 配置管理

#### 1. 环境变量配置
```bash
# .env
DEBUG=true
LOG_LEVEL=INFO
TASK_MAX_WORKERS=4
CACHE_DEFAULT_TTL=3600
```

#### 2. YAML配置
```yaml
# app/config/core_config.yaml
infrastructure:
  tasks:
    max_workers: 4
    retry_attempts: 3
```

#### 3. 代码中使用配置
```python
from app.application.config.settings import get_settings

settings = get_settings()
max_workers = settings.task_max_workers
```

## 🏗️ 架构详解

### 目录结构
```
app/
├── api/                    # API层 - 路由和中间件
├── application/           # 应用层 - 业务逻辑编排
│   ├── handlers/         # 处理器 - 业务流程编排
│   └── services/         # 服务 - 具体业务逻辑
├── domain/               # 领域层 - 核心业务概念
├── infrastructure/       # 基础设施层
│   ├── cache/           # 缓存实现
│   ├── decorators/      # 通用装饰器
│   ├── tasks/           # 任务系统
│   └── external_services/ # 外部服务
├── schemas/             # 数据传输对象
└── config/              # 配置管理
```

### 调用流程
```
HTTP请求 → Router → Handler → Service → Infrastructure
    ↓         ↓        ↓         ↓           ↓
  参数验证  业务编排  具体逻辑  基础设施调用  外部服务
```

### 扩展开发

#### 1. 添加新的API端点
```python
# app/api/v1/routers/my_router.py
from fastapi import APIRouter
from app.application.handlers.my_handler import MyHandler

router = APIRouter(prefix="/my-feature", tags=["我的功能"])

@router.post("/")
async def create_something(data: MyRequest):
    handler = MyHandler()
    return await handler.handle_request(data.dict())
```

#### 2. 添加新的业务服务
```python
# app/application/services/my_service.py
from app.application.services.base_service import BaseService

class MyService(BaseService):
    async def process_business_logic(self, data: dict) -> dict:
        # 实现具体业务逻辑
        return {"result": "processed"}
```

#### 3. 添加新的基础设施组件
```python
# app/infrastructure/external_services/my_service.py
class MyExternalService:
    async def call_external_api(self, data: dict) -> dict:
        # 调用外部服务
        pass
```

## 📊 监控和运维

### 健康检查
- `/api/v1/health` - 完整健康检查
- `/api/v1/health/sync` - 快速健康检查  
- `/api/v1/health/ping` - 简单ping检查

### 任务监控
- `/api/v1/tasks/statistics` - 任务系统统计
- `/api/v1/tasks/registry` - 已注册任务类型
- `/api/v1/tasks/history` - 任务执行历史

### 日志
- 结构化JSON日志
- 请求追踪ID
- 性能指标记录

## 🧪 测试

```bash
# 运行所有测试
make test

# 代码检查
make lint

# 格式化代码
make format
```

## 📝 开发规范

### 代码风格
- 使用Black进行代码格式化
- 使用Ruff进行代码检查
- 使用MyPy进行类型检查

### 提交规范
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 重构代码
- test: 测试相关

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🔗 相关链接

- [FastAPI文档](https://fastapi.tiangolo.com/)
- [Pydantic文档](https://docs.pydantic.dev/)
- [Structlog文档](https://www.structlog.org/)

---

## 🎯 后续计划

- [ ] 数据库集成（SQLAlchemy + Alembic）
- [ ] JWT认证系统
- [ ] Celery分布式任务队列
- [ ] Prometheus指标监控
- [ ] OpenTelemetry链路追踪
- [ ] 自动化部署脚本

## 💡 设计理念

这个框架的设计遵循以下原则：

1. **关注点分离**: 每一层都有明确的职责
2. **依赖倒置**: 高层模块不依赖低层模块
3. **开闭原则**: 对扩展开放，对修改关闭
4. **单一职责**: 每个类和函数都有单一的职责
5. **可测试性**: 易于编写单元测试和集成测试

通过遵循这些原则，框架能够支持复杂业务场景的开发，同时保持代码的可维护性和可扩展性。