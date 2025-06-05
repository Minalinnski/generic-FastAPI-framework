# 测试说明

## 测试结构

```
tests/
├── test_decorators.py      # 装饰器功能测试
├── test_task_system.py     # 任务系统测试
├── test_integration.py     # 集成测试
├── stress_test.py          # 压力测试
├── run_tests.py            # 测试运行器
├── conftest.py             # pytest配置
└── README.md               # 本文件
```

## 运行测试

### 前置要求

1. 安装测试依赖：
```bash
pip install pytest pytest-asyncio httpx
```

2. 启动服务（用于集成测试和压力测试）：
```bash
python -m uvicorn app.main:app --reload
```

### 运行方式

1. **单元测试**（测试装饰器功能）：
```bash
python tests/run_tests.py unit
```

2. **集成测试**（测试API端点）：
```bash
python tests/run_tests.py integration
```

3. **压力测试**（性能和限流测试）：
```bash
python tests/run_tests.py stress
```

4. **所有测试**：
```bash
python tests/run_tests.py all
```

### 直接使用pytest

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_decorators.py -v

# 运行特定测试函数
pytest tests/test_decorators.py::TestRateLimiter::test_sliding_window_rate_limit -v
```

## 测试内容

### 装饰器测试 (test_decorators.py)

- **限流测试**:
  - 滑动窗口算法
  - 令牌桶算法
  - 用户级限流
  - API限流装饰器

- **重试测试**:
  - 简单重试
  - 指数退避
  - 特定异常重试
  - 重试耗尽处理

- **缓存测试**:
  - 缓存命中/未命中
  - 缓存过期
  - 条件缓存

- **压力测试**:
  - 限流器并发测试
  - 重试机制压力测试
  - 组合装饰器测试

### 任务系统测试 (test_task_system.py)

- 任务提交和执行
- 优先级排序
- 任务超时处理
- 任务状态追踪

### 集成测试 (test_integration.py)

- 健康检查端点
- 任务注册表端点
- 任务提交端点
- 完整的API流程测试

### 压力测试 (stress_test.py)

- **健康检查端点压测**: 100并发，1000请求
- **任务提交压测**: 50并发，200任务
- **限流器有效性**: 快速请求验证限流
- **任务执行监控**: 监控任务完成情况
- **混合负载测试**: 多种操作并发执行

## 预期结果

### 正常情况下的测试结果

1. **限流器测试**: 应该看到部分请求被限流（HTTP 429）
2. **重试测试**: 失败的操作应该自动重试并最终成功
3. **缓存测试**: 相同请求应该命中缓存，减少执行时间
4. **任务系统**: 任务应该按优先级执行，超时任务应该被终止
5. **压力测试**: 系统应该在高负载下保持稳定，限流器正常工作

### 性能基准

- **健康检查QPS**: 应该 > 500
- **任务提交QPS**: 应该 > 50
- **平均响应时间**: 健康检查 < 10ms，任务提交 < 100ms
- **成功率**: 正常情况下 > 95%

## 故障排除

1. **服务连接失败**: 确保服务在 localhost:8000 运行
2. **测试超时**: 检查服务性能，可能需要调整超时配置
3. **限流测试失败**: 检查限流配置是否过于宽松
4. **任务系统测试失败**: 检查任务管理器是否正常启动

## 自定义测试

可以修改 `stress_test.py` 中的参数来调整测试强度：

```python
# 调整并发数和请求数
await self.test_health_endpoint_stress(
    concurrent_requests=200,  # 并发数
    total_requests=2000       # 总请求数
)
```