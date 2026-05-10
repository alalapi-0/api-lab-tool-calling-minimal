"""本地工具白名单。

只允许两个工具：
- calculator(expression): 安全四则运算（不允许任意 Python 代码）
- read_note():            只读取仓库内固定文件 note.txt（不允许任意路径）

任何超出白名单的"工具调用"都必须被拒绝。这是 Agent 安全的最小骨架。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent
NOTE_PATH = REPO_ROOT / "note.txt"

# 允许的字符：数字、空格、+ - * / ( ) . 这就够做最简单的算数
_SAFE_EXPR = re.compile(r"^[0-9+\-*/().\s]+$")


def calculator(expression: str) -> dict:
    """安全的四则运算计算器。

    设计原则：
    - 只允许数字 + 空格 + + - * / ( ) .
    - 不调用 eval 完整模式：只用 eval 在限定字符且禁用 builtins 时执行
    - 任何不合法字符直接拒绝
    - 任何异常都被捕获，返回结构化错误
    """
    expr = expression.strip()
    if not expr:
        return {"ok": False, "error": "expression 为空"}
    if len(expr) > 200:
        return {"ok": False, "error": "expression 过长（>200 字符），已拒绝"}
    if not _SAFE_EXPR.match(expr):
        return {
            "ok": False,
            "error": "expression 含非法字符，仅允许数字、空格、+ - * / ( ) .",
        }
    try:
        # 关键：禁用 builtins，等于堵掉了 __import__、open、exec 等
        value = eval(expr, {"__builtins__": {}}, {})
    except ZeroDivisionError:
        return {"ok": False, "error": "除以 0"}
    except Exception as exc:
        return {"ok": False, "error": f"计算失败: {exc.__class__.__name__}: {exc}"}
    return {"ok": True, "result": value, "expression": expr}


def read_note() -> dict:
    """只读取仓库内固定文件 note.txt。"""
    if not NOTE_PATH.exists():
        return {"ok": False, "error": "note.txt 不存在"}
    if not NOTE_PATH.is_file():
        return {"ok": False, "error": "note.txt 不是普通文件"}
    try:
        text = NOTE_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": f"读文件失败: {exc}"}
    return {"ok": True, "path": "note.txt", "content": text}


# 白名单：名字 -> (函数, 该函数预期的参数列表)
TOOLS = {
    "calculator": (calculator, ["expression"]),
    "read_note": (read_note, []),
}


def dispatch(tool_name: str, args: dict) -> dict:
    """根据模型给出的 JSON 决定调用哪个工具。

    严格白名单：
    - tool 不在 TOOLS 里 → 拒绝
    - 缺少必填参数 → 拒绝
    - 多余参数 → 忽略（更友好），但只把白名单内的参数传进去
    """
    if tool_name not in TOOLS:
        return {
            "ok": False,
            "error": f"工具 `{tool_name}` 不在白名单里。允许: {list(TOOLS)}",
        }
    func, expected = TOOLS[tool_name]
    safe_args = {k: args.get(k) for k in expected}
    missing = [k for k, v in safe_args.items() if v is None]
    if missing:
        return {
            "ok": False,
            "error": f"工具 `{tool_name}` 缺少参数: {missing}",
        }
    return func(**safe_args)
