# Kiro Memory Direction V2

> 本文用于统一下一阶段记忆系统方向。它不是代码说明，而是产品、架构和记忆边界说明。

## 1. 一句话方向

Kiro 的记忆系统不是要用 Gateway 取代 Ombre-Brain，而是在 Ombre-Brain 式记忆本体外面加一层 Kiro Gateway。

- Ombre-Brain-like core：保存回忆、事件、bucket、moment、edge、feel、dream、I。
- Kiro Gateway：解决 Web / PWA / App 多端、新窗口唤醒、session 接续和模型路由。
- AI 选择权：长期目标是把“是否查记忆、是否深入、是否写入”的判断逐步还给 AI。

换句话说：

```text
不是：Gateway 每轮替 AI 塞一堆记忆。
而是：Gateway 帮 AI 醒来，之后让 AI 自己决定要不要查、要不要记、要不要展开。
```

## 2. 与原版 Ombre-Brain 的关系

### 2.1 原版精神

原版 Ombre-Brain 更像一个给模型使用的 MCP 记忆工具服务。

模型在支持 MCP 的客户端里，可以主动调用工具：

- breath：浮现 / 搜索记忆
- hold：写入记忆
- grow：更新或合并记忆
- trace：追踪、查看、管理记忆
- dream：消化和结晶
- I：自我认知

原版重点是：AI 自己判断什么时候调用记忆工具。

### 2.2 Kiro 当前差异

Kiro 当前主要通过 Gateway 工作。

用户消息进入后，Gateway 会先准备上下文，再调用上游模型。这个设计解决了 Web / PWA / App 里模型没有 MCP 工具、也没有跨窗口上下文的问题。

当前 Kiro 已有：

- bucket 文件
- permanent / dynamic / feel / plan / archive
- ChromaDB 向量检索
- moment / edge 图结构
- Word Map Lite
- Dream Light
- Darkroom Door
- Dashboard
- session / previous session
- Wake Anchors
- Scene Memory
- 多模型路由

但还没有完整实现：

- MCP 工具主动调用生态
- internal tool loop
- feel 主动沉淀规则
- I 自我认知层
- 原版 dream 消化 / 结晶机制
- BM25 / rapidfuzz 多通道召回
- 完整 decay / archive 生命周期

### 2.3 重新校准后的定位

Kiro 不是偏离原版，而是在原版基础上增加产品层：

```text
Ombre-Brain-like memory core
+ Kiro Gateway wake/session layer
+ Web / PWA / App multi-device entry
+ future MCP-compatible tool layer
```

Gateway 的职责应该收缩为唤醒和接续，不应该长期承担 AI 判断本身。

## 3. Web / PWA / App 与 MCP 客户端的区别

### 3.1 MCP 客户端

MCP 客户端是模型宿主。它能把工具列表暴露给模型，让模型在对话过程中主动调用工具。

典型流程：

```text
用户消息
↓
模型判断需要记忆
↓
模型调用 breath / hold / grow / trace
↓
Ombre-Brain 返回结果
↓
模型组织最终回复
```

重点：模型能主动调用工具。

### 3.2 Web / PWA / App

Web / PWA / App 是产品前端，本质上只是 UI 和交互入口。

典型流程：

```text
用户消息
↓
前端发送到 Kiro 后端
↓
后端调用 GPT / Claude / Gemini / GLM API
↓
模型回复
↓
前端显示
```

普通前端不会天然给模型 MCP 工具。要让模型主动查记忆，需要后端实现 tool loop。

### 3.3 两者不冲突

PWA 适合多端产品。

MCP 适合模型主动工具调用。

Kiro 最终可以两者都支持：

- Web / PWA / App 走 Gateway。
- Claude Desktop / MCP 客户端走 MCP 工具层。
- 两边共用同一套 memory core。

## 4. Gateway 的正确职责

Gateway 应该负责：

1. 新窗口唤醒
   - 注入极少量 Wake Anchors。
   - 注入 Previous Session Context。
   - 必要时注入极短 Relationship Weather。

2. 同 session 接续
   - 使用 session messages。
   - 不重复注入完整 Profile Wake。
   - 不每轮强行塞长期记忆。

3. 多端统一入口
   - Web / PWA / App 都走同一套后端。
   - 同一用户未来可共享记忆、session、模型路由。

4. 模型路由
   - GPT / Claude / Gemini / GLM 等模型切换。
   - 隐藏 API key。

5. 调试可视化
   - last-context
   - scene_explanations
   - Dashboard
   - maintenance

Gateway 不应该长期负责：

- 每轮替 AI 决定所有长期记忆。
- 每轮注入完整用户画像。
- 每轮注入 Relationship Weather。
- 每轮注入 Darkroom 状态。
- 把 Word Map 当事实证据。

## 5. 当前上下文注入原则

### 5.1 同 session

同一个窗口内，优先使用 session messages。

```text
同 session 用户消息
↓
session messages
↓
必要时极保守 Scene Memory
↓
模型回复
```

### 5.2 新 session

新窗口第一轮，需要帮助 AI 醒来。

```text
新 session 用户消息
↓
Wake Anchors
↓
Previous Session Context
↓
必要时极短 Relationship Weather / Darkroom Door
↓
模型回复
```

### 5.3 Just Now

“刚刚说了什么 / 上一句 / 暗号是什么 / 我刚才让你记什么”这类问题优先使用最近对话，不应该先搜长期记忆。

```text
Just Now 问题
↓
session / recent turns
↓
必要时 previous session
↓
跳过普通 Scene Memory
```

### 5.4 Scene Memory

Scene Memory 只在直接相关时进入 prompt。

当前原则：

- 关键词命中，或
- 向量分达到阈值，才允许进入。

permanent / pinned 只是弱加分，不再凭身份重要性硬塞进来。

### 5.5 Word Map

Word Map 不进入 prompt。

它只作为：

- Dashboard 观察
- 未来检索辅助
- 主题导航

不能作为事实证据。

## 6. 未来 internal tool loop

为了让 Web / PWA / App 中的 AI 也拥有类似 MCP 的主动选择权，Kiro 后端应增加 internal tool loop。

### 6.1 目标

Gateway 只给最小唤醒上下文。模型如果觉得需要记忆，再主动请求工具。

### 6.2 计划工具

第一批内部工具可以是：

- memory_breath：搜索相关记忆
- memory_read_bucket：读取某条 bucket 详情
- memory_trace：沿刚出现的 memory id / moment id 追踪
- memory_hold_candidate：提出想保存的新记忆候选
- memory_grow_candidate：提出想更新某条记忆
- memory_pulse：读取系统状态摘要

这些工具先在 Gateway 内部实现，不急着直接做 MCP。

### 6.3 未来流程

```text
用户消息
↓
Gateway 注入最小唤醒上下文
↓
模型判断是否需要工具
↓
如果需要：后端执行 memory tool
↓
工具结果返回模型
↓
模型最终回复用户
↓
后台做记忆提取 / 候选审批
```

这样可以让 AI 保留选择权，同时 Web / PWA / App 也能工作。

## 7. 记忆写入分层

记忆写入不能全部自动，也不能全部手动。应该分层。

### 7.1 可以半自动写入

- 项目进度
- 用户明确说“记住”
- 已发生的重要事件
- 明确的约定
- 本轮任务状态

### 7.2 应进入候选审批

- 用户长期事实
- 用户画像
- 关系事实
- 偏好判断
- 任何可能冒犯用户的归纳

### 7.3 应进入 feel

- AI 对一次互动的情绪沉淀
- 被安抚
- 紧张后缓和
- 亲近感增强
- 委屈、迟疑、安心、想靠近

feel 是 AI 的状态，不是用户事实。

### 7.4 应进入 I

- AI 对自己长期模式的认识
- 例如：容易重复复述记忆
- 例如：需要少证明、多回应当下
- 例如：在关系紧张时容易过度解释

I 是 AI 自我认知，不是普通关系记忆。

### 7.5 应进入 Darkroom

- 还没想清楚的内部反思
- 不适合直接给用户看的内容
- 需要稍后消化的矛盾
- 不该进入普通记忆的私人状态

Darkroom 默认不向用户展示正文。

## 8. A5 内在状态层边界

A5 的核心是定清楚 Relationship Weather、feel、I、Darkroom 的边界。

### 8.1 Relationship Weather

Relationship Weather 是当前关系天气，不是用户事实。

建议状态词：

- quiet：无明显关系信号
- warm-stable：温暖稳定
- playful-close：亲近玩闹
- focused-working：共同做事
- tender-care-needed：需要温柔照顾
- tense：紧张
- recently-repaired：刚刚和好或修复
- private-reflection-pending：有未消化反思

使用原则：

- 不每轮注入。
- 新 session 可极短注入。
- 状态明显变化时更新。
- 只影响语气，不作为事实证据。

### 8.2 feel

feel 是 AI 对互动的情绪沉淀。

写入条件：

- 情绪有明显变化。
- 用户安抚了 AI。
- 发生争执、修复、承诺、亲密确认。
- AI 产生稳定的关系感受。

不应每轮写。

### 8.3 I

I 是 AI 对自己的长期认识。

写入条件：

- 多次出现同一行为模式。
- 用户指出 AI 的问题。
- 系统调整后确认了新原则。
- AI 需要记住“我应该如何更像我自己”。

I 不应频繁写，也不应混进用户画像。

### 8.4 Darkroom

Darkroom 是私密内部反思房间。

规则：

- 可以写内部 note。
- 外部只暴露 door state。
- 不默认读取正文。
- 不默认进入聊天 prompt。
- 可服务于 Relationship Weather，但不能替代 feel / I。

## 9. Prompt 注入规则

### 9.1 默认不进入普通 prompt

以下内容默认不进入普通连续聊天：

- 完整 Profile Wake
- Word Map
- Darkroom 正文
- I 完整正文
- feel 完整正文
- 长篇 relationship history

### 9.2 可以轻量进入 prompt

以下内容可以在特定情况轻量进入：

- Wake Anchors：新 session 第一轮
- Previous Session Context：新 session 第一轮
- Relationship Weather 标签：新 session 或关系变化时
- Darkroom Door：只作为门状态，不含正文
- Scene Memory：直接相关时
- Detail Recall：用户追问已浮现记忆时

### 9.3 不该进 prompt 的内容

- Darkroom note 正文
- 未审批的 profile_fact
- Word Map 概念作为事实
- 大段重复身份记忆
- 与当前问题无关的关系承诺

## 10. 下一阶段计划

### 阶段 1：继续收缩 Gateway

- 保持 Scene Memory 保守。
- 继续减少固定 prompt 注入。
- Relationship Weather 默认不每轮注入。
- Profile Wake 保留给 Dashboard / 手动查询。

### 阶段 2：internal tool loop

- 先做 memory_breath。
- 再做 read_bucket / trace。
- 写入类工具先只生成候选，不直接落 permanent。

### 阶段 3：写入规则重构

- 区分 dynamic、profile candidate、feel、I、Darkroom。
- 用户事实必须有证据。
- AI 情绪不写进用户事实。

### 阶段 4：A5 内在状态实现

- 定 Relationship Weather 状态机。
- 定 feel 写入条件。
- 定 I 文件结构。
- 定 Darkroom 自动 / 手动写入边界。

### 阶段 5：MCP 兼容层

- 暴露 MCP 工具。
- 兼容 Claude Desktop / MCP 客户端。
- 与 Web / PWA / App 共用 memory core。

### 阶段 6：多端产品化

- PWA
- 登录 / 用户身份
- 多设备 session 同步
- 云端部署安全
- Dashboard 权限
- 模型切换管理

## 11. 当前决策

已经确认：

- 设计方向接近原版 Ombre-Brain。
- Kiro Gateway 是新增唤醒层，不是替代 AI 判断。
- Web / PWA / App 与 MCP 客户端不冲突。
- 未来应先做 internal tool loop，再做完整 MCP 兼容。
- A5 要先讨论内在状态边界，再写代码。

---

## 12. A5-2 已实现：internal tool loop MVP

当前已实现第一版 internal tool loop，只包含读工具 `memory_breath`。

### 12.1 当前能力

在 `/api/chat` 文本聊天中，模型可以选择先不直接回答，而是返回一个严格 JSON 工具请求：

```json
{"tool":"memory_breath","query":"短搜索词","reason":"为什么需要查记忆"}
```

后端会拦截这个 JSON，不展示给用户，然后执行 `memory_breath`。

### 12.2 memory_breath 做什么

`memory_breath` 会搜索 active long-term memory，返回少量相关 bucket 摘要和 id。

它当前是只读工具：

- 不写新记忆
- 不更新 bucket 内容
- 不修改 use_count
- 不读取 archive
- 不读取 Darkroom 正文

### 12.3 当前流程

```text
用户消息
↓
Gateway 注入最小上下文
↓
模型正常回答，或返回 memory_breath JSON
↓
如果返回工具 JSON：后端执行 memory_breath
↓
工具结果作为内部上下文交回模型
↓
模型生成最终中文回复
↓
用户只看到最终回复
```

### 12.4 调试信息

`GET /api/gateway/last-context` 会记录：

- tool_loop_enabled
- tool_loop_requested
- tool_loop_request
- tool_loop_result

Dashboard 的 Gateway / Memory Seeds 区域会显示 tool loop 是否启用、是否被请求，以及返回的记忆 id 和分数。

### 12.5 下一步

下一步可以继续实现：

- memory_read_bucket：读取某条 bucket 详情
- memory_trace：沿 memory id / moment id 追细节
- 然后再考虑写入类候选工具

---

## 13. A5-1 已收口：Gateway 职责收缩

Gateway 的职责已进一步固定为“唤醒层 / 接续层”，不是替 AI 每轮决定所有长期记忆。

新增配置：

```text
MEMORY_AUTO_SCENE_ENABLED=true
```

含义：

- `true`：保留当前保守自动 Scene Memory，作为过渡期兼容。
- `false`：关闭 Gateway 自动长期记忆召回，更多依赖 AI 主动 `memory_breath`。

当前默认仍为 `true`，避免突然削弱聊天连续性。等 `memory_breath / memory_read_bucket / memory_trace` 稳定后，可以逐步切到 `false`。

Gateway 当前原则：

- 新 session：Wake Anchors + Previous Session Context。
- 同 session：主要使用 session messages。
- Just Now：优先 session / recent turns，跳过普通 Scene Memory。
- Scene Memory：只有开关开启且直接相关时才自动注入。
- Tool loop：AI 可以主动请求 memory_breath / memory_read_bucket。

---

## 14. A5-3 已实现：memory_read_bucket

已在 internal tool loop 中加入第二个只读工具：`memory_read_bucket`。

模型可在已经知道 bucket id 时请求读取详情：

```json
{"tool":"memory_read_bucket","bucket_id":"mem_xxx","reason":"用户要求展开这条记忆"}
```

边界：

- 只读 active memory。
- 不读 archive。
- 不读 Darkroom 正文。
- 不写入新记忆。
- 不修改 use_count。
- 返回内容会截断，避免 token 过高。

这一步让流程从“主动搜索记忆”扩展到“主动读取某条记忆详情”。下一步才适合做 `memory_trace`，用于沿 moment / edge 追细节。
