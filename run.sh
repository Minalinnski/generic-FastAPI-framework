#!/bin/bash

# 设置错误时退出
set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}FastAPI DDD Framework 启动脚本${NC}"

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}错误: 需要Python $required_version 或更高版本，当前版本: $python_version${NC}"
    exit 1
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: .env 文件不存在，创建默认配置...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}请编辑 .env 文件配置您的环境变量${NC}"
fi

# 激活虚拟环境或提示创建
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

echo -e "${GREEN}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${GREEN}安装依赖...${NC}"
pip install -e ".[dev]"

# 运行代码检查（可选）
if [ "$1" = "--check" ]; then
    echo -e "${GREEN}运行代码检查...${NC}"
    ruff check app/
    black --check app/
    mypy app/
fi

# 启动服务
echo -e "${GREEN}启动FastAPI服务...${NC}"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

if [ "$1" = "--prod" ]; then
    echo -e "${GREEN}生产模式启动...${NC}"
    export ENVIRONMENT=production
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
else
    echo -e "${GREEN}开发模式启动...${NC}"
    export ENVIRONMENT=development
    export DEBUG=true
    export RELOAD=true
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
fi