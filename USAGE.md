# Vision Dataset Studio 使用说明

本文用于把项目打包成 ZIP 分享后，接收者解压并通过 Codex 或终端启动使用。

## 1. 项目用途

这是一个面向视觉训练数据的专业预处理工具，主要用于：

- 浏览 `control1 / control2 / control3 / result` 多图数据集
- 编辑自然语言 Caption
- 批量添加、删除、替换 Caption 短语
- 使用本地 Qwen、Ollama 或 OpenAI 兼容 API 自动标注
- 标注前批量缩放裁切图片
- 非破坏性导出已完成数据集为 ZIP 或文件夹

默认不会直接改动原始图片目录。Caption 编辑、AI 标注、排除导出等内容会保存到项目工作副本中，导出时再生成新的数据集。

## 2. 解压后目录

推荐解压到一个没有中文空格问题的路径，例如：

```text
/home/yourname/Codex/vision-dataset-studio
```

或 WSL 下访问 Windows 磁盘：

```text
/mnt/d/projects/vision-dataset-studio
```

项目关键文件：

```text
README.md                       完整功能说明
USAGE.md                        当前快速使用说明
install.sh                      Linux / WSL 预安装脚本
install.bat                     Windows 预安装脚本
start.sh                        推荐 Linux / WSL 启动脚本
run.sh                          固定 127.0.0.1:8100 启动脚本
run.bat                         Windows 启动脚本
web_server.py                   Web 服务入口
web_index.html                  页面结构
web_app.js                      前端逻辑
web_styles.css                  页面样式
```

## 3. 首次安装环境

项目默认使用项目内 `.venv`，不会把依赖装到 Conda 或系统 Python。

推荐先预安装基础环境：

```bash
./install.sh
```

如果你希望本地 Qwen 也一次装好，可以执行：

```bash
./install.sh --with-qwen
```

Windows 下可执行：

```text
install.bat
```

或：

```text
install.bat --with-qwen
```

如果只使用基础编辑、图像处理、API 标注或 Ollama 标注，基础环境通常够用。本地 Qwen 仍可在网页里点击“安装依赖”，也可以在预安装阶段直接用 `--with-qwen` 装好。

## 4. 启动 Web 工作台

### WSL / Linux

推荐：

```bash
./start.sh
```

或：

```bash
./run.sh
```

启动后打开：

```text
http://127.0.0.1:8100
```

### Windows

双击：

```text
run.bat
```

启动后打开：

```text
http://127.0.0.1:8100
```

### 更换端口

如果 8100 被占用：

```bash
PORT=8101 ./start.sh
```

然后访问：

```text
http://127.0.0.1:8101
```

### 局域网访问

如果希望同一局域网其他设备访问：

```bash
HOST=0.0.0.0 PORT=8100 ./start.sh
```

然后用本机局域网 IP 加端口访问。注意防火墙可能需要放行。

## 5. 基本使用流程

1. 打开网页。
2. 点击顶部右侧的 `数据`。
3. 在目录浏览器中输入父目录，逐级选择子目录。
4. 按数据集结构填入：
   - `控制图 1`
   - 可选 `控制图 2`
   - 可选 `控制图 3`
   - `结果图`
5. 设置 `控制图数量`。
6. 点击 `加载工作区`。
7. 在左侧列表选择图片。
8. 在中间浏览 control / result 图片。
9. 在下方 Caption 编辑区直接编辑自然语言描述。
10. 点击 `保存`。

如果新增或复制了图片到目录中，点击 `重扫工作区` 刷新列表。

## 6. AI 自动标注

顶部命令栏有统一标注入口：

- `标注引擎`：选择 `本地 Qwen / Ollama / OpenAI 兼容 API`
- `标注当前`：对当前图片标注
- `批量标注`：对当前筛选列表批量标注
- `停止`：停止批量任务
- `标注设置`：打开右侧配置面板

### OpenAI 兼容 API

1. 点击 `标注设置`。
2. 在 `OpenAI 兼容 API 标注` 中填写：
   - `API Base URL`
   - `API Key`
3. 点击 `刷新模型`。
4. 选择或填写模型名。
5. 可点击 `验证 API`。
6. 顶部 `标注引擎` 选择 `OpenAI 兼容 API`。
7. 点击 `标注当前` 或 `批量标注`。

`API Key` 会保存在当前浏览器 localStorage 中。分享 ZIP 时不会包含对方浏览器里的 API Key。

### Ollama

1. 启动本机 Ollama。
2. 在 `标注设置` 中填写 Ollama URL，例如：

```text
http://127.0.0.1:11434
```

3. 点击 `读取模型`。
4. 选择或填写支持图像输入的模型。
5. 顶部 `标注引擎` 选择 `Ollama`。
6. 点击 `标注当前` 或 `批量标注`。

### 本地 Qwen

1. 在 `标注设置` 中选择 Qwen3.5 模型。
2. 若之前没有执行 `install.sh --with-qwen` / `install.bat --with-qwen`，首次使用点击 `安装依赖`。
3. 点击 `加载模型`。
4. 点击 `验证模型`。
5. 顶部 `标注引擎` 选择 `本地 Qwen`。
6. 点击 `标注当前` 或 `批量标注`。

本地模型默认使用项目内目录：

```text
models/<模型名>
```

例如：

```text
models/Qwen3.5-4B
```

如果检测到旧的 `~/ComfyUI/models/LLM/<模型名>` 目录或旧版 `models/huggingface` 缓存，也会兼容复用；否则首次加载时会自动下载到项目 `models` 目录。

## 7. 图像处理

如果图片过大，建议先处理图像再标注，节省 API token 或本地显存。

流程：

1. 点击 `图像处理`。
2. 输入工作集名称，例如 `越野风格`。
3. 选择目标像素，默认 `4 百万像素`。
4. 选择尺寸倍数：`16 / 32 / 64`。
5. 保持 `处理完成后加载为当前工作区` 勾选。
6. 点击 `处理图像工作集`。

处理使用 Lanczos 缩放并中心裁切。完成后会生成新的工作集，不会覆盖原始目录。

## 8. 导出数据集

标注完成后：

1. 点击 `导出`。
2. 输入项目名称，例如 `越野风格`。
3. 选择导出格式：
   - `下载 ZIP`
   - `导出为文件夹`
4. 按需选择是否再次缩放裁切图片。
5. 点击 `导出数据集`。

导出的目录命名格式类似：

```text
日期时间_项目名_control1
日期时间_项目名_result
```

如果启用了多个控制图，会生成对应的 `control2 / control3` 目录。对应 control 和 result 会保持同一 basename，便于训练工具匹配。

## 9. 打包分享建议

打包 ZIP 前建议保留：

```text
*.py
*.html
*.js
*.css
*.sh
*.bat
*.yml
README.md
USAGE.md
prompt_templates.example.json
```

按需保留：

```text
prompt_templates.json
```

不建议打包：

```text
models/
datasets/
__pycache__/
```

原因：

- `models/` 通常很大，可由接收者本地准备或下载。
- `datasets/` 可能包含你的私有图片数据、已保存项目、工作副本、导出结果或中间文件。
- `datasets/projects/` 是正式保存的项目；`datasets/tmp/` 是过程文件，服务启动后会自动清理过期内容。
- API Key 保存在浏览器 localStorage，不在项目文件中；但仍建议打包前检查项目目录里没有手动写入的密钥文件。

如果接收者会通过 Codex 启动，可以让他对 Codex 说：

```text
请阅读 USAGE.md，帮我创建环境并启动这个项目。
```

## 10. 常见问题

### 浏览器打不开

检查服务是否启动成功，默认地址是：

```text
http://127.0.0.1:8100
```

如果端口被占用，换端口启动：

```bash
PORT=8101 ./start.sh
```

### 页面能打开但没有数据

需要先在 `数据` 面板加载控制图和结果图目录。

### API 刷新模型失败

检查：

- `API Base URL` 是否正确，通常形如 `https://.../v1`
- `API Key` 是否正确
- 当前服务是否支持 `/models` 接口

如果模型列表接口不兼容，也可以直接手动输入模型名。

### 批量标注没有变化

检查：

- 当前筛选结果是否为空
- `已有 TXT` 设置是否为 `跳过`
- 日志里是否有 API、Ollama 或本地模型错误

### 图像处理后原始目录没变化

这是正常行为。项目默认非破坏性处理，会生成新的工作集或导出目录，不覆盖原图。
