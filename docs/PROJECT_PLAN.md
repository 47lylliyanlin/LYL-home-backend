# Kiro 项目计划大纲

> 一个基于语音对话的 AI 助手，有记忆系统，能记住你的喜好、对话历史、关系状态和项目进度。

---

## 📋 项目阶段总览

### ✅ 阶段一：基础环境搭建（已完成）
**目标：** 搭建前后端开发环境，验证基本功能。

**完成内容：**
- ✅ 安装 Python 环境和依赖
- ✅ 创建 FastAPI 后端服务
- ✅ 创建简单前端页面
- ✅ 测试前后端通信

---

### ✅ 阶段二：语音功能实现（已完成）
**目标：** 实现语音输入和语音输出功能。

**完成内容：**
- ✅ 语音识别（STT）- 使用本地 FunASR 模型
- ✅ 语音合成（TTS）- 支持本地/ElevenLabs 配置
- ✅ 前端录音功能
- ✅ 前端音频播放功能
- ✅ 语音对话流程打通

---

### ✅ 阶段三：基础记忆系统搭建（已完成）
**目标：** 让 AI 能保存和检索用户信息、对话历史、项目进度。

**完成内容：**
- ✅ 实现 Ombre-Brain 风格记忆系统
- ✅ 记忆分类：permanent / dynamic / feel / plan / letter / archive
- ✅ 情感坐标：valence / arousal
- ✅ 记忆衰减和归档机制
- ✅ 对话后自动提取记忆
- ✅ 向量检索 + 关键词 + 分数排序
- ✅ 导入本地记忆资料
- ✅ 记忆维护脚本

**技术实现：**
- ChromaDB 向量数据库
- Markdown 记忆桶
- 自动提取对话中的关键信息
- 记忆分数 = importance + 使用频率 - 时间衰减
- 低分 dynamic 记忆自动归档

---

### ✅ 阶段四：UI 优化（已完成）
**目标：** 优化用户界面和交互体验。

**完成内容：**
- ✅ 聊天界面美化
- ✅ 语音播放条
- ✅ 加载动画
- ✅ 错误提示优化
- ✅ 用户和 AI 消息样式区分

---

### ✅ 阶段五：聊天记录持久化（已完成）
**目标：** 保存本地聊天记录，刷新页面后不丢失。

**完成内容：**
- ✅ 使用 localStorage 保存聊天记录
- ✅ 页面加载时自动恢复聊天记录
- ✅ 清空聊天记录功能

---

### ✅ 阶段六：代码版本管理（已完成）
**目标：** 使用 Git 管理代码，推送到 GitHub。

**完成内容：**
- ✅ 创建 GitHub 仓库（前端 + 后端）
- ✅ 初始化 Git 仓库
- ✅ 推送代码到 GitHub
- ✅ 生成 requirements.txt
- ✅ 配置 .gitignore

**仓库地址：**
- 前端：https://github.com/47lylliyanlin/LYL-home-frontend
- 后端：https://github.com/47lylliyanlin/LYL-home-backend

---

### ⏳ 阶段七：云服务器部署（进行中）
**目标：** 将项目部署到云端，实现稳定在线访问。

**计划内容：**
- ⏳ 选择部署方案（VPS / Railway / 其他方案）
- ⏳ 配置部署环境
- ⏳ 部署前端
- ⏳ 部署后端
- ⏳ 配置域名和 HTTPS
- ⏳ 测试线上功能
- ⏳ 给 Dashboard 增加访问控制
- ⏳ 明确哪些 memory/runtime 数据不能上传 GitHub

**当前状态：** 本地功能已具备测试条件，部署前需要先做安全整理。

---

### ✅ 阶段八：记忆系统优化（已完成）
**目标：** 把简单记忆检索升级为 Gateway 型长期记忆系统，让 AI 在新窗口、跨客户端、短期追问时都能保持连续感，同时减少主动复述记忆。

**已完成：**
- ✅ Ombre Gateway：普通聊天请求先经过 Gateway，由 Gateway 决定本轮需要注入哪些上下文
- ✅ Wake Context：新窗口优先恢复 Persona、User Portrait、Relationship Portrait、Recent Continuity、少量 Wake Anchors、Darkroom Door
- ✅ Just Now Chat Context：刚刚、上一句、暗号、关键词等问题优先走最近聊天，不去长期记忆里乱搜
- ✅ Profile 画像层：用户画像、AI 自身状态、关系画像、最近连续性、profile fact 候选分层管理
- ✅ Profile Fact 审批：候选事实需要人工批准后才进入 User Portrait，避免模型随口写死长期事实
- ✅ Moment / Edge 图结构：支持 updates、supports、blocks、promises、continues、evidence、diffuses 等关系边
- ✅ Graph Diffusion：只有先命中可靠 direct seed，才允许沿图带出少量低置信背景
- ✅ Word Map Lite：从 bucket / moment 生成概念词图，只作为弱召回辅助，不作为事实证据
- ✅ Darkroom：AI 的内部反思空间，只暴露门状态，不暴露正文
- ✅ Dream Light：生成关系天气，参与浅层维护，不读取 Darkroom 正文
- ✅ Dashboard：可视化 Gateway 注入层、direct seeds、wake anchors、diffused memories、Word Map hints、画像候选审批、Dream、Darkroom、Pulse
- ✅ 维护入口：新增 `/api/maintenance/run` 和 Windows 菜单脚本 `ob.ps1`
- ✅ 多模型切换：支持 Claude 官方、GPT/OpenAI 官方、OpenAI-compatible 中转、Gemini 官方 native API

**技术实现：**
- `api/gateway.py`：统一聊天入口前的上下文组织
- `api/profile.py`：画像与候选审批
- `api/memory_graph.py`：moment / edge 图结构与细节召回
- `api/word_map.py`：Word Map Lite 概念图
- `api/darkroom.py`：Darkroom 门状态与私密笔记入口
- `api/dream.py`：Dream Light 和关系天气
- `api/pulse.py`：系统状态与 introspection
- `api/ai_client.py`：多模型 Provider 切换
- `dashboard/index.html`：记忆系统可视化面板
- `tools/migrate_buckets_v2.py`：旧桶格式 dry-run / apply 转换工具

**当前状态：** 本地功能已经可以测试。下一步重点不再是搭框架，而是观察真实对话质量、调整召回阈值、补部署安全。

---

### ⏳ 阶段九：真实体验优化（待开始）
**目标：** 根据真实聊天效果继续打磨体验。

**计划内容：**
- ⏳ 观察记忆是否太多、太少、太啰嗦
- ⏳ 调整 Just Now 触发词
- ⏳ 调整 graph diffusion 数量和阈值
- ⏳ 优化 Word Map 中文分词和概念过滤
- ⏳ 增加更清楚的模型切换提示和错误提示
- ⏳ 语音消息长按显示识别文字
- ⏳ 导出聊天记录
- ⏳ 个性化设置（主题、语音速度、模型选择等）

---

### ⏳ 阶段十：性能与稳定性优化（待开始）
**目标：** 提升响应速度、稳定性和部署后的可维护性。

**计划内容：**
- ⏳ 给 Gemini / GPT / Claude 增加失败重试和模型降级
- ⏳ 给 Dream / Word Map 增加定时维护
- ⏳ 语音识别优化，减少延迟
- ⏳ 语音合成优化，支持更稳定的输出
- ⏳ 前端资源压缩
- ⏳ 数据库查询和记忆检索优化
- ⏳ 部署后的日志、备份、健康检查

---

## 🧪 当前测试清单

1. **普通连续性测试**
   - 提问：“我们现在在做什么？”
   - 预期：自然回答当前项目进度，不主动复述一大堆记忆。

2. **Just Now 测试**
   - 先说：“暗号是蓝色月亮。”
   - 再问：“刚刚的暗号是什么？”
   - 预期：Dashboard 中 Just Now 开启，Scene Memory 关闭。

3. **Wake 测试**
   - 刷新页面或新开窗口。
   - 提问：“你知道我是谁吗？我们最近在做什么？”
   - 预期：优先使用 Profile 和 Recent Continuity。

4. **Dashboard 测试**
   - 打开 `http://localhost:8000/dashboard/`
   - 查看 Gateway Injection Layers、Memory Seeds、Profile Fact Approval、Dream、Darkroom、Word Map、AI Routing。

5. **维护测试**
   - Dashboard 点击 Maintenance，或运行 `ob.ps1` 第 8 项。
   - 预期：Word Map 重建、Dream Light 运行，Darkroom 正文不被读取。

---

## 🛠 技术栈总览

### 前端
- **HTML/CSS/JavaScript** - 基础网页技术
- **浏览器 API** - MediaRecorder、Audio、localStorage

### 后端
- **Python 3.11** - 编程语言
- **FastAPI** - Web 框架
- **FunASR** - 语音识别
- **MeloTTS / ElevenLabs** - 语音合成
- **ChromaDB** - 向量数据库
- **Markdown 文件** - 记忆桶存储
- **Claude / GPT / Gemini** - 可切换 AI 模型

### 部署（待定）
- **方案 A：** VPS + Nginx + Supervisor
- **方案 B：** Railway / Render / 其他托管平台
- **方案 C：** 本地长期运行 + 内网穿透（仅测试用）

---

## 📝 后续任务清单

### 高优先级
1. 完成真实聊天测试，记录记忆召回问题
2. 决定部署方案
3. 部署前安全整理：密钥、Dashboard、memory/runtime 数据
4. 给模型调用增加失败重试和降级策略

### 中优先级
5. 优化 Word Map 中文概念提取
6. 增加定时维护任务
7. 增加聊天导出功能
8. 完善错误处理和模型切换提示

### 低优先级
9. 用户认证系统
10. 多设备同步
11. 个性化设置
12. 移动端适配

---

## 📚 学习资源

### 云服务器部署相关
- Linux 基础命令
- SSH 连接和密钥管理
- Nginx 反向代理配置
- SSL 证书申请（Let's Encrypt）
- 进程守护（PM2 / Supervisor）

### 记忆系统相关
- 向量数据库原理
- Embedding 嵌入向量
- RAG（检索增强生成）
- 图结构召回
- 画像事实审批

### 前端优化
- Service Worker（离线缓存）
- IndexedDB（本地数据库）
- WebSocket（实时通信）

---

## 🎯 项目愿景

**短期目标（1个月内）：**
- 完成记忆系统真实聊天测试
- 部署上线或形成稳定本地运行方案
- 让 AI 能自然记住用户重要信息，而不是生硬复述记忆

**中期目标（3个月内）：**
- 添加用户系统，支持多用户或多设备
- 完善导出记录、个性化设置、模型选择
- 提升响应速度和稳定性

**长期目标（半年以上）：**
- 多模态交互（图片、视频）
- 智能提醒和长期计划陪伴
- 移动端 App
- 开源或半开源社区版本

---

## 📞 联系方式

- GitHub：https://github.com/47lylliyanlin
- 项目前端：https://github.com/47lylliyanlin/LYL-home-frontend
- 项目后端：https://github.com/47lylliyanlin/LYL-home-backend

---

**最后更新：** 2026年6月26日

---

## 🔍 对照原版 Ombre-Brain 的剩余差距（2026年6月30日）

参考原版 `INTERNALS.md` 后，当前项目和原版仍有以下差异。这里按“是否必要”标注优先级。

### 1. MCP 工具主动调用机制

**原版：** 模型通过 `breath / hold / grow / trace / dream / plan / letter / I` 等 MCP 工具主动读写记忆。

**当前：** 我们走 Gateway 普通聊天路线，模型不直接调用 MCP 工具，Gateway 在模型调用前整理上下文，回复后自动提取记忆。

**是否必要：** 中期必要。当前 Web 聊天可以先继续用 Gateway；如果以后要接 Claude Desktop、Claude.ai 或更接近原版体验，需要补 MCP 工具层。

### 2. feel 桶与 I 自我认知

**原版：** `feel` 是模型自己的情绪沉淀，普通 breath 不浮现；`I` 是模型对自我规律、局限和变化的认知。

**当前：** 有 `feel` 类型目录和 Darkroom 概念，但没有完整实现原版 `hold(feel=True)` 和 `I()` 主动写入机制。

**是否必要：** 有必要，但不属于当前 Gateway 稳定阶段。建议放入“内在状态层”阶段，先定义 AI 自身记忆和用户记忆的边界。

### 3. Darkroom 与原版差异

**原版：** 公开 INTERNALS 没有 Darkroom 主线模块，近似能力由 `feel` 和 `I` 承担。

**当前：** Darkroom 是扩展出来的私密反思房间，只暴露门状态，不暴露正文。当前只有主动接口写入，不会自动写。

**是否必要：** 可保留，但不应频繁进入聊天 prompt。更适合后续作为 feel/I 之外的私密缓冲区。

### 4. 多通道召回

**原版：** rapidfuzz、BM25、embedding、衰减分共同进入召回/排序；embedding 不是唯一召回入口。

**当前：** 关键词 + ChromaDB 向量 + calculate_score 排序，BM25/rapidfuzz 还没有按原版完整补齐。

**是否必要：** 中期必要。当前 Scene Memory 可用，但容易被 permanent/pinned/use_count 影响。后续应补更稳的候选池和阈值。

### 5. 衰减、归档和 touch 细节

**原版：** dynamic 会衰减，permanent/feel/plan/letter 有不同生命周期；浮现模式不 touch，检索命中才 touch。

**当前：** 已有衰减和归档雏形，但运行策略、维护周期、Dashboard 操作还不完整。

**是否必要：** 必要。真实使用后 memory 会越来越多，必须有维护和归档机制。

### 6. Dream 的消化机制

**原版：** dream 用于候选、提示、消化和结晶；feel 可参与结晶检测。

**当前：** Dream Light 只做浅层关系天气和状态整理，不读取 Darkroom 正文。

**是否必要：** 中期必要。当前 Dream Light 可保留为轻量状态；深度 dream 可等记忆数据稳定后再做。

### 7. Dashboard 与部署安全

**原版：** Dashboard、认证、OAuth、远程 MCP、备份同步、环境变量说明较完整。

**当前：** Dashboard 有基础状态与维护能力，但鉴权、远程部署安全、备份恢复、OAuth/MCP 还未完整。

**是否必要：** 云端部署前必要。至少要完成密钥清理、Dashboard 鉴权、备份和健康检查。

### 建议阶段

- **当前阶段：** 稳定 Gateway、session、模型路由、记忆召回质量和 token 消耗。
- **下一阶段：** 清理重复测试记忆，补强维护工具和 Dashboard 安全。
- **内在状态阶段：** 补原版 feel / I 机制，重新定义 Darkroom 与 Relationship Weather 的边界。
- **原版兼容阶段：** 增加 MCP 工具层、BM25/rapidfuzz、多通道召回和远程部署能力。
