# Vision Dataset Studio

视觉数据集工作台，面向视觉训练数据的专业预处理平台。

用于视觉训练数据集的多图浏览、自然语言 Caption 编辑、批量整理、图像预处理、质检与 AI 标注辅助。

如果你是通过 ZIP 收到这个项目，建议先阅读 [USAGE.md](USAGE.md)，里面包含解压、创建环境、启动、AI 标注、图像处理、导出和打包分享注意事项。

当前默认入口是 **Web GUI**，支持：

- 多控制图数据集浏览
- 追加额外图像对数据集到当前工作区
- Caption 编辑、翻译、批量处理
- 非破坏性工作副本保存与数据集导出
- 历史项目保存 / 打开 / 克隆 / 重命名，并恢复项目 UI 状态
- 标注前图像预处理、导出时图像缩放 / 中心裁切 / 尺寸倍数约束
- 本地 Qwen3.5 多模型标注
- OpenAI 兼容 API 标注
- Ollama 多模态标注
- Prompt 模板存储、选择、删除

默认监听：

- `127.0.0.1:8100`
- 本机访问：`http://127.0.0.1:8100`
- 需要局域网访问时，启动时显式指定 `--host 0.0.0.0`

旧版 `Tkinter` 界面已归档在 `legacy/`，默认开发和维护目标是 Web 版。

---

## 1. 功能概览

### 1.1 工作区

工作区由以下目录组成：

- `控制图1`
- `控制图2`
- `控制图3`
- `结果图`

其中：

- `结果图` 是主要目标目录
- `控制图数量` 可以设置为 `0 / 1 / 2 / 3`
- 当控制图数量为 `0` 时：
  - 只显示和标注 `结果图`
  - 不提示缺失任何控制图
- 当控制图数量为 `1` 时：
  - 默认显示 `控制图1 + 结果图`
  - 不会提示缺失控制图2/3
- 当控制图数量切换为 `2` 或 `3` 时：
  - 浏览区会自动切换到三图或四图模式
  - 缺失筛选会按当前启用数量生效

工作区面板支持“追加图像对数据集”：

- 可把额外的 `control1/control2/control3/result` 目录追加进当前工作区
- 追加时不会清空当前已载入条目
- 与现有条目同名时会自动生成唯一显示名，例如 `sample [2]`
- 追加内容只影响当前工作区会话，原始目录不会被改写

### 1.2 文件名匹配

本项目不再要求完全同名匹配，而是使用更鲁棒的规则进行归并。

匹配思路：

- 以图像和 `.txt` 的“同 basename 对应”作为基础规则
- 自动忽略常见角色后缀/前缀，例如：
  - `control1`
  - `control2`
  - `control3`
  - `ctrl1 / ctrl2 / ctrl3`
  - `input1 / input2 / input3`
  - `result`
  - `output`
  - `target`
  - `final`
  - `edited`
  - 中文的 `控制图1/2/3`、`结果图`
- 允许用户手动增加“匹配忽略项”，例如：
  - `_result`
  - `_output`
  - `-edited`
  - `_final`

这套规则的目标是兼容训练工具常见的数据集组织方式，例如 `ostris/ai-toolkit` 这类“图像与 caption 使用同 basename 对应”的模式，再扩展到多目录控制图场景。

### 1.3 浏览与编辑

浏览区支持：

- 单图：只看结果图
- 双图：控制图1 + 结果图
- 三图：控制图1 + 控制图2 + 结果图
- 四图：控制图1 + 控制图2 + 控制图3 + 结果图

编辑区支持：

- Caption 文本直接编辑
- 短语级增删改
- 保存 caption（默认写入项目工作副本，不改动原始目录）
- 翻译当前 caption
- 快捷标注按钮

列表区支持：

- 全部
- 缺控制图1
- 缺控制图2
- 缺控制图3
- 缺结果
- 缺 TXT
- 分辨率异
- 短语 / Caption 搜索

键盘支持：

- `↑` / `↓` 在浏览区切换上一条 / 下一条数据

### 1.4 AI 标注

支持三条标注通道：

#### 本地 Qwen3.5

- 本地模型：
  - `Qwen3.5-0.8B`
  - `Qwen3.5-2B`
  - `Qwen3.5-4B`
  - `Qwen3.5-9B`
  - `Qwen3.5-27B`
- 支持模型加载
- 支持模型验证
- 支持单张 / 批量标注
- 支持多图输入
- 默认使用项目内 `models/<模型名>` 目录
- 若检测到旧的 `~/ComfyUI/models/LLM/<模型名>` 目录或旧缓存，会兼容复用
- 若本地不存在，则首次加载时自动下载到项目 `models` 目录

#### OpenAI 兼容 API

- 支持多模态 OpenAI 兼容接口
- 填入 `API Base URL` 与 `API Key` 后，可手动刷新模型列表并选择模型
- 模型名右侧箭头可展开模型菜单；当下方空间不足时，菜单会自动向上弹出
- 支持验证
- 支持单张 / 批量标注
- 支持多图输入

#### Ollama

- 通过本地网址调用 Ollama，例如：
  - `http://127.0.0.1:11434`
- 支持读取模型列表
- 模型名右侧箭头可展开模型菜单；当下方空间不足时，菜单会自动向上弹出
- 支持验证
- 支持单张 / 批量标注
- 支持多图输入

### 1.5 Prompt 模板

支持 Prompt 模板：

- 模板列表读取
- 套用模板
- 保存为模板
- 删除模板

默认内置模板包括：

- `中文·极简变化`
  - `仅描述控制图1到结果图的变化，极简描述，中文描述。`
- `中文·多图差异`
  - `结合所有控制图与结果图，仅描述控制图到结果图的主要变化，忽略未变化内容，极简描述，中文输出。`
- `English·Vision Short`

模板应用在通用 Prompt 区，本地 Qwen、API、Ollama 会共用同一组生成参数。

### 1.6 图像预处理与导出

图像处理与导出模块默认采用非破坏性工作流：

- 原始图片目录和原始 `.txt` 不会被改写
- 手动编辑、AI 标注和批量整理会写入项目内工作副本
- “从导出集中排除当前条目”只影响导出结果，不删除源文件

标注前可先在“图像处理”面板生成处理后的工作集：

- 使用 Lanczos 缩放并中心裁切图片
- 目标像素：`1 / 2 / 3 / 4` 百万像素，默认 `4` 百万像素
- 输出尺寸约束为 `16 / 32 / 64` 的倍数
- 可选择同时处理当前启用的控制图目录
- 可选择处理完成后直接加载为当前工作区，用于后续 AI 标注
- 图像处理会显示逐条进度、当前文件和处理日志

本地 / API / Ollama 标注、批量标注和图像处理共用任务状态区：

- 批量标注显示 `done / total` 进度
- 图像处理显示真实逐条进度
- 单张 API / Ollama / 本地标注请求会在请求期间保持进度提示
- 顶部 `停止` 按钮可停止批量标注；本地 Qwen 模型加载中点击它也会取消加载 / 下载进程

导出时可选择：

- 下载 ZIP
- 导出为服务器本地文件夹
- 项目名称，用于生成 ZIP / 文件夹前缀
- 是否按图像处理面板的参数再次缩放并中心裁切图片
- 是否同时导出当前启用的控制图目录

导出内容包含：

- `日期时间_项目名_result`，包含结果图与同名 `.txt`
- 可选的 `日期时间_项目名_control1 / control2 / control3` 控制图目录
- `manifest.json` 导出清单

同一条数据导出时会统一重命名，确保 `control*` 与 `result` 中对应文件保持相同 basename。

---

## 2. 环境要求

### 2.1 推荐环境

- Windows 10 / 11
- WSL2
- Python：`3.11` 推荐，支持 `>=3.10,<3.13`
- 项目会在当前目录自动创建 `.venv`，基础依赖和本地 Qwen 依赖都安装到该目录，不写入 Conda 或系统 Python

### 2.2 AI 相关

本地 Qwen 推荐：

- NVIDIA 显卡
- CUDA 可用

如果只使用 API / Ollama，可不依赖本地 CUDA。

---

## 3. 启动方式

### 3.1 WSL / Linux

首次创建环境：

```bash
conda env create -f environment.caption-codex.yml
```

启动 Web GUI：

```bash
./run.sh
```

如需局域网访问：

```bash
conda run -n caption-codex python web_server.py --host 0.0.0.0 --port 8100
```

启动归档的旧版桌面 GUI：

```bash
./legacy/run_legacy.sh
```

### 3.2 Windows

双击：

- `run.bat`
- `legacy/run_legacy.bat`

如果系统已安装 Conda，脚本会优先使用 `caption-codex` 环境。

如需局域网访问，手动用命令启动并指定 `--host 0.0.0.0`。

---

## 4. 路径输入规则

### 4.1 支持的路径格式

Web 界面里的目录输入支持：

- Linux / WSL 路径
  - `/mnt/d/dataset/control1`
- Windows 路径
  - `D:\dataset\control1`
  - `C:\Users\name\Pictures\dataset`
- `~` 家目录路径

Windows 路径会自动转换为 WSL 可访问路径，例如：

- `D:\dataset\control1` -> `/mnt/d/dataset/control1`
- `C:\Users\me\Pictures` -> `/mnt/c/Users/me/Pictures`

### 4.2 重扫工作区

当你正在往目录里大量导入图片时：

- 当前页面不会自动监听文件系统变化
- 看到“缺失部分数据”不等于导入失败
- 很可能只是扫描快照还没更新

这时可以点击：

- `重扫工作区`

它会按当前的：

- 控制图数量
- 匹配忽略项
- 控制图目录 / 结果图目录

重新扫描并刷新列表。

---

## 5. 首次使用本地 Qwen

### 5.1 最简单流程

1. 启动 Web GUI
2. 点击顶部命令栏的 `标注配置`
3. 在 `标注引擎` 的 `本地标注` 页里：
   - 选择模型
   - 点击 `安装 Qwen 依赖到 .venv`
   - 点击 `加载模型`
   - 点击 `验证模型`
4. 通过后再做单张或批量标注

### 5.2 本地模型目录优先级

本地 Qwen 默认使用项目内目录：

```text
models/<模型名>
```

例如：

```text
models/Qwen3.5-0.8B
```

若项目目录存在且结构完整，会直接加载，不重复下载。

若检测到旧的 `~/ComfyUI/models/LLM/<模型名>` 目录或旧版 `models/huggingface` 缓存，也会兼容复用。

### 5.3 手动安装依赖

网页里的 `安装 Qwen 依赖到 .venv` 会自动确认/创建项目 `.venv`，并只使用 `.venv` 的 Python 安装。若需要手动安装本地 Qwen 依赖，先确认已通过 `./start.sh` 或 `run.bat` 创建 `.venv`，再执行：

```bash
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
.venv/bin/python -m pip install --upgrade -r requirements-qwen-common.txt
.venv/bin/python -m pip install --upgrade git+https://github.com/huggingface/transformers.git@main
```

---

## 6. 多图差异标注说明

### 6.1 当前行为

本地 Qwen、OpenAI 兼容 API、Ollama 三条链路现在都支持多图输入。

传图顺序是：

1. 当前启用的控制图
2. 结果图

例如：

- 控制图数量 = 0：
  - `result`
- 控制图数量 = 1：
  - `control1`
  - `result`
- 控制图数量 = 2：
  - `control1`
  - `control2`
  - `result`
- 控制图数量 = 3：
  - `control1`
  - `control2`
  - `control3`
  - `result`

### 6.2 适合的 Prompt

如果你希望只描述变化，推荐直接使用内置模板：

```text
仅描述控制图1到结果图的变化，极简描述，中文描述。
```

或：

```text
结合所有控制图与结果图，仅描述控制图到结果图的主要变化，忽略未变化内容，极简描述，中文输出。
```

---

## 7. 批量操作

支持：

- 批量添加短语
- 批量删除短语
- 批量替换短语
- 从导出集中排除当前条目

排除当前条目时：

- 不删除原始控制图、结果图或同名 `.txt`
- 只影响当前工作副本和后续导出结果

---

## 8. 项目保存

项目面板支持保存当前工作区为可再次打开的项目：

- 保存当前项目 / 另存为新项目
- 打开历史项目
- 重命名、克隆、删除项目
- 保存当前控制图数量、匹配忽略项、标注配置、Prompt、筛选状态、选择条目和快捷标注

项目文件默认保存在用户目录：

```text
~/.vision_dataset_studio/projects/
```

删除项目会移动到：

```text
~/.vision_dataset_studio/trash/
```

---

## 9. 项目结构

```text
server/                    后端入口与任务调度目录
server/web_server.py       Web GUI 服务主实现
server/caption_workflow.py 标注任务、写回策略与 modify 模式逻辑
server/image_process_jobs.py 图像处理后台任务管理
web_server.py              根目录兼容启动入口
caption_workflow.py        根目录兼容导入包装
image_process_jobs.py      根目录兼容导入包装
frontend/                  前端辅助模块目录
frontend/web_shared.js     前端共享常量、存储与请求工具
frontend/web_projects.js   前端项目管理模块
frontend/web_workspace.js  前端工作区浏览与路径填充模块
frontend/web_image_ops.js  前端图像处理与导出模块
frontend/web_caption.js    前端标注后端、模型菜单与 AI 状态模块
frontend/web_editor.js     前端编辑区、快捷标注与批量短语模块
frontend/web_browser.js    前端列表、筛选、Viewer 与工作区动作模块
frontend/web_shell.js      前端壳层、面板切换与活动后端选择模块
frontend/web_bootstrap.js  前端设置恢复、事件绑定与启动模块
web_index.html             前端页面
web_app.js                 前端交互逻辑
web_styles.css             前端样式
dataset_workspace.py       工作区扫描 / 匹配 / 筛选 / 读写
dataset_projects.py        历史项目保存 / 打开 / 管理
dataset_paths.py           datasets 路径与 tmp 清理
caption_client.py          本地 AI 子进程客户端
caption_service.py         本地 Qwen3.5 推理服务
api_caption_client.py      OpenAI 兼容 API 客户端
ollama_caption_client.py   Ollama 客户端
prompt_templates.py        Prompt 模板存储逻辑
qwen_models.py             本地 Qwen 模型注册表
bootstrap_env.py           创建 / 维护项目 .venv
requirements-base.txt      Web GUI 基础依赖
requirements-qwen-common.txt
requirements-qwen-cu124.txt
run.sh
run.bat
legacy/                   归档的旧版 Tkinter GUI 与启动脚本
models/                    项目内 Qwen 模型目录与内部缓存
~/.vision_dataset_studio/projects/ 保存后的正式项目
~/.vision_dataset_studio/trash/    删除项目的回收目录
datasets/tmp/              中间过程文件，启动后每日自动清理过期内容
datasets/exports/          导出结果
datasets/workspaces/       工作区状态
```

---

## 10. 已知限制

### 10.1 工作区不是实时监听

大量文件导入时：

- 列表不会自动发现新文件
- 需要点击 `重扫工作区`

### 10.2 多图理解能力取决于模型

虽然代码已支持多图输入，但不同模型对“多图差异理解”的效果差异很大：

- 本地小模型更适合做简短变化描述
- 更复杂的跨图关系，建议用更大 Qwen 模型或强一些的 API 模型

### 10.3 Ollama 需要模型本身支持图像输入

不是所有 Ollama 模型都支持多模态。

---

## 11. 常见问题

### Q: 浏览器打不开 8100 端口？

检查：

- 服务是否仍在运行
- 防火墙是否拦截
- 端口是否被占用

### Q: 导入中看到缺图，是不是导入失败？

不一定。

常见原因：

- 文件还在复制中
- 文件名尚未完全对齐
- 当前列表还是旧扫描结果

先点击：

- `重扫工作区`

再看结果。

### Q: 只上传了控制图1，为什么之前会提示缺控制图2/3？

现在不会了。

缺失提示已经按“当前启用的控制图数量”计算：

- 控制图数量 = 0，不提示缺任何控制图
- 控制图数量 = 1，不提示缺控制图2/3
- 控制图数量 = 2，不提示缺控制图3

### Q: Windows 路径为什么以前不能用？

现在已经支持直接输入：

- `D:\...`
- `C:\...`

会自动转换为 WSL 路径。

### Q: 本地 Qwen 验证失败？

先检查：

1. `caption-codex` 环境是否正常
2. 是否已经点击 `安装 Qwen 依赖到 .venv`
3. 本地模型目录是否存在，或网络是否可下载
4. 显卡 / CUDA 是否可用

### Q: Ollama 验证失败？

检查：

- `Ollama URL` 是否正确
- 本机 Ollama 服务是否启动
- 你填写的模型是否支持图像输入

### Q: Prompt 模板在哪里保存？

模板保存在项目目录下的：

- `prompt_templates.json`

推荐提交到仓库的是：

- `prompt_templates.example.json`

如果文件不存在，会使用内置默认模板。

---

## 12. 调试建议

如果你要继续扩展这个项目，建议优先从这几处看：

- 文件匹配规则：
  - [dataset_workspace.py](dataset_workspace.py)
- 多图本地标注：
  - [caption_service.py](caption_service.py)
  - [caption_client.py](caption_client.py)
  - [web_server.py](web_server.py)
- Prompt 模板：
  - [prompt_templates.py](prompt_templates.py)
- 前端工作区 / 浏览区 / 模板 UI：
  - [web_app.js](web_app.js)
  - [web_index.html](web_index.html)
  - [web_styles.css](web_styles.css)
