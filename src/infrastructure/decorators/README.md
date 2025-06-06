```
# 装饰器执行顺序示例和最佳实践

# 推荐的装饰器顺序（从上到下）：
@router.post("/example")
@api_rate_limit(requests_per_minute=30)  # 1. 最外层：流量控制
@simple_retry(attempts=3, delay=1)       # 2. 中间层：重试机制
@async_task(priority=1, timeout=300)     # 3. 最内层：任务管理
async def example_api():
    """业务逻辑"""
    pass

# 执行流程：
# Request → Rate Limit → Retry → Task → Business Logic
#                ↓
# Response ← Rate Limit ← Retry ← Task ← Business Logic

# 各装饰器的职责：
"""
1. @api_rate_limit: 
   - 控制请求频率
   - 防止系统过载
   - 在最外层拦截过多请求

2. @simple_retry:
   - 处理瞬时故障
   - 网络问题重试
   - 在Task层之外，避免重复提交任务

3. @async_task/@sync_task:
   - 任务队列管理
   - 并发控制
   - 优先级调度
   - 最接近业务逻辑

为什么这个顺序？
- Rate Limit 在最外层：避免无效请求进入系统
- Retry 在中间：如果Task提交失败可以重试
- Task 在最内层：确保每次重试都是完整的业务逻辑执行
"""

# 实际应用示例：

# 高频简单操作
@router.get("/foo/status")
@api_rate_limit(requests_per_minute=100)
@sync_task(timeout=5)
async def get_status():
    pass

# 中频复杂操作  
@router.post("/foo/process")
@api_rate_limit(requests_per_minute=30)
@simple_retry(attempts=2)
@async_task(priority=1, timeout=300)
async def complex_process():
    pass

# 低频关键操作
@router.post("/foo/critical")
@api_rate_limit(requests_per_minute=5)
@network_retry(attempts=5)  # 使用更强的重试
@high_priority_task(timeout=600)
async def critical_operation():
    pass
```