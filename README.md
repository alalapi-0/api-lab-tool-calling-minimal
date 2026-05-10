# api-lab-tool-calling-minimal

> 最小化体验：「模型出主意，本地动手」是怎么回事。

## 工具调用到底是什么

很多人第一次听到「模型能调用工具」时会以为：
> 「模型自己跑去执行命令了？」

**不是。** 真实情况是：

1. 你给模型说明一组**它能用的工具**和**调用约定**（例如「请输出 JSON，结构是 {tool, args}」）
2. 模型只是**生成一段文本**，里面描述「我想调用哪个工具、传什么参数」
3. 你的本地程序**解析这段文本**，对照**白名单**决定要不要真的执行
4. 工具的真正执行**始终在你这台机器上**，模型从头到尾没碰过文件系统

也就是说：**模型 = 出主意的人，本地代码 = 真正动手的人。**
所有 Agent 的安全核心，就在那个白名单。

## 这个仓库做了什么

最简实现：

- 我们**不用**任何厂商的 tool-calling 协议（OpenAI 的 `tools`、Anthropic 的 `tool_use` 等都不用）
- 直接在 system prompt 里告诉模型：「请只输出 JSON，结构是 {tool, args}」
- 我们用 `requests` 发一次 chat 请求，把模型的输出**当 JSON 解析**
- 本地白名单 `tools.py` 决定要不要执行

只有两个工具被允许：

| 工具 | 行为 | 防御 |
| --- | --- | --- |
| `calculator(expression)` | 算简单算式 | 字符正则白名单；`eval` 时禁用 `__builtins__`；超长拒绝 |
| `read_note()` | 读取仓库内固定 `note.txt` | 路径写死，根本不接受参数 |

## 运行步骤

```bash
cd api-lab-tool-calling-minimal
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，三选一：
#   OpenRouter:  AI_BASE_URL=https://openrouter.ai/api/v1, AI_MODEL=openai/gpt-4o-mini
#   DeepSeek:    AI_BASE_URL=https://api.deepseek.com/v1,  AI_MODEL=deepseek-chat
#   LM Studio:   AI_BASE_URL=http://localhost:1234/v1,     AI_MODEL=（本地模型名）
# 模型不一定听话，建议用偏稳定的中等以上模型

python3 main.py
cat output/result.json
```

## 用户问题（写死在 main.py）

> 请计算 12 * 8 + 3。

期望流程：

1. 模型输出 `{"tool": "calculator", "args": {"expression": "12 * 8 + 3"}}`
2. 本地白名单接受 → 执行 → 返回 `99`

如果你想让模型选 `read_note`，把 `USER_QUESTION` 改成例如「请把 note.txt 的内容读出来」。

## 模型常见失败模式（很有教育意义）

| 现象 | 解释 | 怎么办 |
| --- | --- | --- |
| 模型不输出纯 JSON，加了一堆解释 | 指令服从性差，特别是某些低成本模型 | 换更好的模型，或在 system prompt 里更狠地强调 |
| 模型输出的 JSON 用了 markdown ```json 包裹 | 它非要展示 | 本仓库的 `extract_json` 已做最小宽容 |
| 模型自己编了第三个工具名 | 它"想象力丰富" | 白名单直接拒绝，不会执行；这正是白名单的价值 |
| 模型在 expression 里塞 Python 代码 | 它在偷渡 | 白名单只放过 `[0-9+\-*/().\s]`，且 `eval` 禁用 `__builtins__` |

## .env.example

```
AI_API_KEY=填入你的API Key
AI_BASE_URL=https://example.com/v1
AI_MODEL=填入模型名
```

## 安全声明（很重要）

- **没有任何"模型自动执行任意代码"的入口。** 所有外部输入都必须通过 `tools.dispatch`。
- `calculator` 的 `eval` 在禁用 `__builtins__` 的 sandbox 里跑，且字符已被正则白名单过滤。
- `read_note` 完全不接受参数，路径写死在 `tools.py`。
- 真要扩展工具，请**先**写一个新的安全函数 + 加入 `TOOLS` 白名单，再改 system prompt。

## 不会做的事

- 不会接外部真实工具（不会发邮件、不会跑 shell、不会写文件）
- 不会做多轮对话循环（只单次"模型出意图 → 本地执行"）
- 不会自动重试
- 不会打印 API Key
