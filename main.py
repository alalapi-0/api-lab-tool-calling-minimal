"""api-lab-tool-calling-minimal

体验「带工具的小模型/工具调用」的最小骨架，**不用任何厂商的 tool calling 协议**。

流程：
1) 我们告诉模型：你只能输出一段严格的 JSON，描述你想调用哪个工具
2) 模型返回一段文本，我们把它当 JSON 解析
3) 本地程序根据白名单执行那个工具
4) 把工具结果打印 + 写入 output/

这就是绝大多数 Agent 的最小雏形：
    模型 = 出主意的人
    本地代码 = 真正动手的人（被白名单约束）

本仓库只允许两个本地工具（详见 tools.py）：
    - calculator(expression)   只允许数字和 + - * / ( ) .
    - read_note()              只读仓库内 note.txt
任何越界都会被拒绝。
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import tools

USER_QUESTION = "请计算 12 * 8 + 3。"

SYSTEM_PROMPT = """你是一个会用工具的助手。
你只能在以下两个工具中二选一调用：

1) calculator(expression: string)
   - 计算简单算式
   - expression 只允许包含数字和 + - * / ( ) . 和空格

2) read_note()
   - 读取项目内的 note.txt

你的回答**必须是一个严格的 JSON 对象**，结构如下：

{"tool": "<工具名>", "args": {<参数键值对>}}

例子：
- {"tool": "calculator", "args": {"expression": "1 + 2"}}
- {"tool": "read_note", "args": {}}

不要输出额外的说明文字，不要包裹在代码块里，不要解释，只输出 JSON。"""

TIMEOUT_SECONDS = 30
MAX_TOKENS = 100


def call_model(api_key: str, base_url: str, model: str) -> str:
    """让模型返回一段 JSON 文本。"""
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_QUESTION},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """模型有时会偷偷包代码块或加废话；这里做最小宽容解析。"""
    text = text.strip()
    # 去掉 ```json ... ``` / ``` ... ```
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # 提取从第一个 { 到最后一个 } 的部分（粗暴但够用）
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"模型输出里没找到 JSON 对象。原文: {text[:200]}")
    blob = text[start : end + 1]
    return json.loads(blob)


def main() -> int:
    load_dotenv()

    api_key = os.getenv("AI_API_KEY", "").strip()
    base_url = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("AI_MODEL", "").strip()

    missing = [k for k, v in {
        "AI_API_KEY": api_key,
        "AI_BASE_URL": base_url,
        "AI_MODEL": model,
    }.items() if not v]
    if missing:
        print(f"[错误] .env 缺少以下变量: {', '.join(missing)}")
        print("       请运行: cp .env.example .env，然后填好后再运行。")
        return 2

    print(f"[信息] base_url = {base_url}")
    print(f"[信息] model    = {model}")
    print(f"[信息] 用户问题: {USER_QUESTION}")

    started = time.time()
    try:
        raw = call_model(api_key, base_url, model)
    except requests.exceptions.Timeout:
        print(f"[失败] 请求超时（{TIMEOUT_SECONDS}s）。")
        return 1
    except requests.exceptions.RequestException as exc:
        print(f"[失败] 网络请求异常: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"[失败] 模型调用错误: {exc}")
        return 1
    elapsed = time.time() - started

    print()
    print("[信息] 模型原始输出（理论上是一段 JSON）:")
    print(raw)
    print()

    try:
        intent = extract_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[失败] 解析模型 JSON 意图失败: {exc}")
        print('        提示：换一个对指令更服从的模型，或在 prompt 里再强调「只输出 JSON」。')
        return 1

    tool_name = intent.get("tool", "")
    args = intent.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    print(f"[信息] 模型意图: tool={tool_name}, args={args}")

    tool_result = tools.dispatch(tool_name, args)
    print(f"[信息] 工具执行结果: {tool_result}")

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    record = {
        "user_question": USER_QUESTION,
        "model": model,
        "elapsed_seconds": round(elapsed, 3),
        "model_raw_output": raw,
        "parsed_intent": intent,
        "tool_executed": tool_name,
        "tool_args": args,
        "tool_result": tool_result,
    }
    out_file = out_dir / "result.json"
    out_file.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[信息] 已写入 {out_file}（不会被 git 提交）")

    if tool_result.get("ok"):
        print("[成功] 走完一个最小 Agent 循环：模型生成意图 → 本地白名单执行。")
        return 0
    print("[提示] 工具执行被拒绝或失败（这本身也是预期内的：白名单生效）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
