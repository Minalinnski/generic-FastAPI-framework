import re
from pathlib import Path

root = Path("app")
for py_file in root.rglob("*.py"):
    with open(py_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 修改第一行注释路径
    if lines and lines[0].startswith("#"):
        lines[0] = lines[0].replace("app/", "src/", 1)

    # 修改 from app. 的 import 语句
    lines = [re.sub(r'\bfrom\s+app(\.[\w\.]*)', r'from src\1', line) for line in lines]

    # 保存修改
    with open(py_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
