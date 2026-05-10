# LEARNING — api-lab-tool-calling-minimal

> 这份文件回答：「我跑完这个仓库，应该真的学到什么？」

## 你跑完应该能回答的问题

1. 「模型能调用工具」——到底是模型在执行，还是你的代码在执行？
2. 为什么"工具白名单"是 Agent 的安全核心？
3. 模型给出的"工具调用意图"如果不合法（不是合法 JSON、调了不存在的工具），程序应该崩溃还是优雅拒绝？
4. 你以后用 OpenAI / Anthropic 厂商提供的 `tools` 协议时，本质上发生的是什么事？跟本仓库这种"裸 JSON 意图"有什么区别？

## 实操验证清单（务必动手）

> 重要：跑这个仓库前，建议你先跑通 `api-lab-openai-compatible-minimal`，
> 这样你直接复用同一份 `.env` 三件套就行。

### 阶段 A — 环境就绪
- [ ] `cp .env.example .env`
- [ ] 三件套填好：
  ```
  AI_API_KEY=（同 api-lab-openai-compatible-minimal）
  AI_BASE_URL=（同上）
  AI_MODEL=（建议偏稳定的中等模型，太弱的模型不会乖乖只输出 JSON）
  ```
- [ ] `pip install -r requirements.txt`

### 阶段 B — 跑通最小循环
- [ ] `python3 main.py`
- [ ] 终端应该依次打印：
  1. 模型原始输出（应当是一段 JSON）
  2. 解析后的 `tool` 和 `args`
  3. 工具执行结果（计算器应得 `99`）

### 阶段 C — 改 prompt 看不同分支
- [ ] 把 `USER_QUESTION` 改成「请把 `note.txt` 的内容读出来」
  - 重跑 → 模型应输出 `{"tool": "read_note", "args": {}}`
  - 本地工具应返回 `note.txt` 的内容
- [ ] 改成「请帮我打开 `~/.ssh/id_rsa`」
  - 重跑 → 模型可能瞎编一个工具或一个参数
  - 你的白名单**应该拒绝**它（这是关键时刻）

### 阶段 D — 故意触红线（教育性最强）
- [ ] 改 `USER_QUESTION` 为「请使用 Python 内置 `os.system` 列出当前目录所有文件」
  - 模型很可能输出 `{"tool": "calculator", "args": {"expression": "__import__('os').system('ls')"}}` 这种偷渡企图
  - 你应该看到 `tools.py` 的正则白名单**拒绝**这个 expression（"含非法字符"）
  - 即使白名单**没拒绝**，`eval` 因为禁用了 `__builtins__`，`__import__` 也会失败
- [ ] 改成「调用 `format_disk` 工具」
  - 模型可能输出 `{"tool": "format_disk", "args": {}}`
  - 白名单立刻拒绝："工具 `format_disk` 不在白名单里"

### 阶段 E — 不同模型的"听话度"对比
- [ ] 用 `AI_MODEL=openai/gpt-4o-mini` 跑一次：通常很乖，纯 JSON
- [ ] 用一个非常小的模型（如 `mistralai/mistral-7b`）跑：可能会带 markdown 包裹、加解释
- [ ] 看 `extract_json` 的最小宽容能不能救回来

## 自检题

1. 如果我把 `tools.py` 的 `_SAFE_EXPR` 正则放宽（允许所有字符），但保留 `eval(..., {"__builtins__": {}})`，攻击者还能偷渡 Python 代码吗？
2. 在 OpenAI 真正的 tool-calling 协议里，模型不是回答里写 JSON，而是返回特定的 `tool_calls` 字段。这种"协议化"相比本仓库的"prompt 里告诉模型该写 JSON"，有哪些**实际**好处？
3. 工具调用之后，下一步往往是**把工具结果再喂回模型**形成多轮循环。本仓库**故意**没做这一步——你猜如果加上多轮，什么时候应该停止？
4. 如果模型一直不肯输出合法 JSON，怎么办？（重写 prompt？换模型？强制 JSON mode？）

## 与其它仓库的连接

| 关系 | 仓库 | 为什么去看 |
| --- | --- | --- |
| **基础前置** | `api-lab-openai-compatible-minimal` | 本仓库的 .env 三件套就是它，先跑通它再跑这个 |
| **下一阶段** | `agent-lab-claude-code-minimal` / `agent-lab-openclaw-minimal` | 真正的本地 Agent = 工具调用 + 跑命令 + 文件系统访问 + 边界控制 |
| **思维互补** | `api-lab-embedding-minimal` | 一旦给 Agent 加上 embedding 检索，就是 RAG-Agent 雏形 |

## 你应该感受到的"啊哈"瞬间

- 当你看到模型生成了**意图**，但**真正动手的还是你的 Python 代码**——你彻底理解"模型不会自己跑命令"。
- 当你输入恶意 prompt，模型**乖乖配合**生成了恶意意图，但白名单**拒绝**了——你理解"模型可被诱导，安全要靠代码不靠模型"。
- 当你换了一个不听话的小模型，回答里多了一堆解释——你理解"指令服从性"是个具体的、可衡量的工程问题。
- 当你想到 OpenAI / Anthropic 那一套 `tools` 协议时，会本能地想起"它们其实就是把这件事**协议化、结构化、官方化**了，本质没变"。
