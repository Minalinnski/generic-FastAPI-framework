# tests/conftest.py
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import asyncio
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    yield loop
    
    # 清理
    try:
        loop.close()
    except:
        pass


@pytest.fixture
async def app():
    """创建测试应用"""
    app = create_app()
    return app


@pytest.fixture(autouse=True)
def setup_logging():
    """设置测试日志"""
    from app.infrastructure.logging.logger import setup_logging
    setup_logging()