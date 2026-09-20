# 发票信息批量提取工具

基于 `pdfplumber` 的电子发票(增值税电子发票 / 机动车销售统一发票)信息批量提取工具,支持 **CLI 命令行**、**PyQt5 桌面 GUI**、**Flask Web 网页** 三种使用方式,可批量解析 PDF 发票并输出结构化的 Excel / CSV 数据。

## 功能特性

- 批量扫描指定目录(含服务器共享盘 UNC 路径)下的 PDF 发票文件
- 自动提取发票关键字段:
  - 发票号码、发票代码、开票日期
  - 销售方 / 购买方名称及纳税人识别号
  - 商品明细(商品名称、规格型号、单位、数量、单价、金额)
  - 税率、税额、价税合计
  - 车辆识别代号 / 车架号码(机动车发票专属,识别 `LFM` 开头的 17 位 VIN 码)
- 每行商品单独生成一条记录,便于明细核算
- 多策略提取:优先文本提取,失败时回退到表格提取
- 支持 Excel(`.xlsx`)和 CSV 两种输出格式
- Excel 输出自动设置表头样式、列宽与数字格式
- 三种使用方式:
  - **CLI**:批处理脚本、定时任务
  - **GUI**:本地可视化操作,进度条 + 日志
  - **Web**:浏览器访问,内网共享,支持目录浏览器与文件上传
- Web 版实时进度推送(SSE),不阻塞界面
- 自动记录提取失败的文件并填充 `提取失败` 占位,保证输出表行对齐

## 目录结构

```
InvoiceRecognition/
├── invoice_extractor.py  # 发票信息提取核心类(三种入口共用)
├── exporter.py           # Excel/CSV 写入逻辑(CLI 与 Web 共用)
├── main.py               # 命令行入口(CLI)
├── gui.py                # 图形界面入口(PyQt5)
├── web_app.py            # Web 后端入口(Flask + SSE)
├── templates/
│   └── index.html        # Web 前端页面(Bootstrap 5)
├── static/
│   ├── app.js            # Web 前端交互(目录浏览/SSE/上传)
│   └── style.css         # Web 页面样式
├── uploads/              # Web 上传文件临时目录(自动创建)
├── outputs/              # Web 生成的 Excel 输出目录(自动创建)
├── requirements.txt      # 依赖清单
├── venv/                 # 本地虚拟环境(可选)
└── README.md             # 项目说明文档
```

## 依赖环境

详见 [requirements.txt](requirements.txt):

| 依赖 | 用途 | 最低版本 | 使用入口 |
| --- | --- | --- | --- |
| pdfplumber | PDF 文本与表格提取(底层基于 pdfminer.six) | 0.10.2 | 全部 |
| openpyxl | 生成 Excel 输出文件 | 3.1.2 | 全部 |
| PyQt5 | 图形界面 | 5.15.0 | gui.py |
| Flask | Web 后端框架 | 3.0 | web_app.py |
| Werkzeug | WSGI 工具库(Flask 依赖) | 3.0 | web_app.py |

安装依赖:

```bash
pip install -r requirements.txt
```

## 使用方式

### 一、命令行模式(CLI)

```bash
python main.py <input_path> [--format {csv,xlsx}] [--output <output_path>]
```

参数说明:

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `input_path` | 是 | 单个 PDF 文件路径,或包含 PDF 的文件夹路径 |
| `-f / --format` | 否 | 输出格式,`csv` 或 `xlsx`,默认 `xlsx` |
| `-o / --output` | 否 | 输出文件路径;不指定则按 `发票信息_时间戳.{ext}` 命名 |

示例:

```bash
# 处理单个 PDF,默认输出 xlsx 到脚本所在目录
python main.py "D:\发票\发票1.pdf"

# 处理整个文件夹,输出 CSV 到指定路径
python main.py "D:\发票\" -f csv -o "D:\输出\result.csv"
```

### 二、图形界面模式(GUI)

```bash
python gui.py
```

界面操作:

1. 点击 **选择文件/文件夹**,可多选 PDF 文件或选择文件夹(自动扫描其中的 PDF)
2. 选中的文件列表显示在日志区域
3. 点击 **开始提取**,进度条和日志显示处理过程
4. 完成后自动弹出输出文件路径,可点击 **打开输出目录** 直接跳转

### 三、Web 网页模式(推荐用于内网共享)

```bash
python web_app.py
```

启动后浏览器访问 **http://localhost:5000**,两种使用方式:

**方式 A:目录浏览器(推荐)**

1. 页面加载后自动显示白名单根目录列表
2. 逐层点击进入子目录,面包屑显示当前路径
3. 到达目标目录后,点击 **扫描此路径** 列出 PDF 清单
4. 点击 **开始提取** 启动后台处理
5. 实时进度条 + 黑色日志区显示处理状态
6. 完成后出现 **下载 Excel** 按钮

**方式 B:文件上传**

1. 切换到「上传文件」标签页
2. 选择多个 PDF 文件
3. 点击 **开始提取** 上传并处理

#### Web 模式配置

**白名单根目录**:在 [web_app.py](web_app.py#L25-L31) 的 `ALLOWED_ROOTS` 中配置可浏览的根目录:

```python
ALLOWED_ROOTS = [
    r'D:\\',
    r'E:\\',
    # r'\\\\server\\share',  # 服务器共享盘 UNC 路径
    os.path.expanduser('~'),
]
```

`/browse` 接口严格校验请求路径必须以白名单根目录为前缀,防止目录穿越攻击。

**端口修改**:在 [web_app.py](web_app.py#L207) 修改 `app.run()` 中的 `port=5000`。

**服务器共享盘访问**:Web 后端运行账号需有 UNC 路径读权限。如访问 `\\server\share` 报错,可用有权限的账号启动:

```cmd
runas /user:domain\user "venv\Scripts\python.exe web_app.py"
```

## 输出字段

输出表格包含以下 18 个字段,与 [exporter.py](exporter.py#L8-L13) / [main.py](main.py#L97-L99) / [gui.py](gui.py#L76-L78) 中定义的 `headers` 一致:

| 列序 | 字段名 | 说明 |
| --- | --- | --- |
| 1 | 文件名 | PDF 文件名 |
| 2 | 发票号码 | 16-20 位数字 |
| 3 | 发票代码 | 10-12 位数字 |
| 4 | 开票日期 | 统一格式化为 `YYYY-MM-DD` |
| 5 | 销售方 | 公司名称 |
| 6 | 销售方税号 | 统一社会信用代码 |
| 7 | 购买方 | 公司名称 |
| 8 | 购买方税号 | 统一社会信用代码 |
| 9 | 商品名称 | 形如 `*机动车*XXX` |
| 10 | 规格型号 | 通常为空 |
| 11 | 单位 | 默认 `辆` |
| 12 | 数量 | 默认 `1` |
| 13 | 单价 | 保留两位小数 |
| 14 | 金额 | 保留两位小数 |
| 15 | 税率 | 如 `13%` |
| 16 | 税额 | 保留两位小数 |
| 17 | 价税合计 | 保留两位小数 |
| 18 | 车辆识别代号/车架号码 | 17 位 VIN 码 |

## 核心模块说明

### invoice_extractor.py

核心类 `InvoiceExtractor`,负责单张发票 PDF 的解析,三种入口共用。

主要方法:

| 方法 | 说明 |
| --- | --- |
| [`__init__(pdf_path)`](invoice_extractor.py#L11-L14) | 初始化时一次性提取文本与表格 |
| [`_extract_text()`](invoice_extractor.py#L16-L27) | 使用 `pdfplumber` 提取所有页文本 |
| [`_extract_tables()`](invoice_extractor.py#L29-L40) | 使用 `pdfplumber` 提取所有页表格 |
| [`extract_invoice_number()`](invoice_extractor.py#L42-L52) | 提取发票号码 |
| [`extract_invoice_code()`](invoice_extractor.py#L54-L64) | 提取发票代码 |
| [`extract_invoice_date()`](invoice_extractor.py#L66-L79) | 提取开票日期并统一格式 |
| [`extract_seller()`](invoice_extractor.py#L81-L103) | 提取销售方名称 |
| [`extract_seller_tax_id()`](invoice_extractor.py#L105-L125) | 提取销售方税号 |
| [`extract_buyer()`](invoice_extractor.py#L127-L148) | 提取购买方名称 |
| [`extract_buyer_tax_id()`](invoice_extractor.py#L150-L190) | 提取购买方税号 |
| [`extract_tax_rate()`](invoice_extractor.py#L192-L203) | 提取税率 |
| [`extract_items_from_text()`](invoice_extractor.py#L221-L266) | 从文本提取商品明细(优先) |
| [`extract_items_from_tables()`](invoice_extractor.py#L268-L309) | 从表格提取商品明细(回退方案) |
| [`calculate_item_prices()`](invoice_extractor.py#L311-L341) | 计算每行不含税金额、税额、价税合计 |
| [`extract_all_rows()`](invoice_extractor.py#L343-L406) | 主入口,每行商品生成一条记录 |
| [`extract_invoice_info()`](invoice_extractor.py#L408-L418) | 提取发票基本信息(不含明细) |

实现要点:

- **性能优化**:在 [`__init__`](invoice_extractor.py#L11-L14) 中一次性打开 PDF 并缓存 `text` 与 `tables`,避免重复 IO
- **多策略提取**:商品明细优先从文本提取(更准确),失败时回退到表格提取
- **税额计算**:若 PDF 中已包含税额则直接使用,否则按 `金额 / (1 + 税率)` 反推不含税金额
- **Decimal 精度**:使用 `Decimal` + `ROUND_HALF_UP` 保证金额计算精度,避免浮点误差

### exporter.py

从 [main.py](main.py#L119-L174) 抽离的 Excel/CSV 写入逻辑,CLI 与 Web 共用,主要函数:

| 函数 | 说明 |
| --- | --- |
| [`write_to_excel(data, filepath)`](exporter.py#L34-L62) | 写入 Excel,自动设置表头样式、列宽、数字格式 |
| [`write_to_csv(data, filepath)`](exporter.py#L28-L32) | 写入 CSV,使用 `utf-8-sig` 编码防中文乱码 |
| [`write_data(data, filepath, fmt)`](exporter.py#L65-L70) | 统一导出入口,`fmt` 为 `'xlsx'` 或 `'csv'` |

### main.py

命令行入口,主要流程:

1. 通过 `argparse` 解析参数(`input_path`、`--format`、`--output`)
2. 判断输入是单个 PDF 文件还是目录,收集待处理文件列表
3. 遍历 PDF,调用 `InvoiceExtractor.extract_all_rows()` 提取数据
4. 失败文件填充 `提取失败` 占位,保证表行对齐
5. 调用 `exporter.write_to_excel()` 或 `write_to_csv()` 输出结果
6. 输出文件路径默认使用 `发票信息_{时间戳}.xlsx` 命名

### gui.py

PyQt5 图形界面,主要组件:

- [`WorkerThread`](gui.py#L15-L93):继承 `QThread`,在工作线程中执行提取任务,通过信号 `progress` / `finished` / `log` 与主线程通信,避免界面卡顿
- [`MainWindow`](gui.py#L96-L291):主窗口,包含文件选择、进度显示、日志输出、处理控制等 UI 元素,提供扁平化样式表

### web_app.py

Flask Web 后端,7 条路由 + SSE 实时进度推送:

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| [`/`](web_app.py#L109-L111) | GET | 首页,渲染前端页面 |
| [`/browse`](web_app.py#L114-L153) | POST | 目录浏览器,列出指定目录下的子目录(白名单校验) |
| [`/scan`](web_app.py#L156-L163) | POST | 扫描目录,返回 PDF 清单(不启动处理) |
| [`/process-path`](web_app.py#L166-L181) | POST | 按目录路径启动处理(支持 UNC 共享盘) |
| [`/upload`](web_app.py#L184-L205) | POST | 接收多文件上传并启动处理 |
| [`/progress/<task_id>`](web_app.py#L208-L233) | GET | SSE 流,实时推送 log/progress/done/error 事件 |
| [`/download/<filename>`](web_app.py#L236-L243) | GET | 下载生成的 Excel |

实现要点:

- **后台线程**:用 `threading.Thread(daemon=True)` 在后台执行提取任务,Flask 主线程继续响应其他请求
- **SSE 推送**:用 `queue.Queue` 在工作线程与 HTTP 流间传消息,浏览器原生 `EventSource` 接收
- **安全设计**:`ALLOWED_ROOTS` 白名单限制可浏览目录,防目录穿越攻击
- **单机部署**:`app.run(threaded=True)`,无需 Redis/Celery,单机内部使用足够

## 常见问题

### 1. 提取出的字段为空

- 确认 PDF 为电子发票(文本可选),非扫描件
- 部分字段(如销售方)依赖特定关键词匹配(如 `惠州`、`厦门`),如发票格式差异较大,可能需要调整 [invoice_extractor.py](invoice_extractor.py) 中对应正则或关键词

### 2. `pdfplumber` 提取失败

- 检查 PDF 是否加密,可先用其他工具解密
- 确认 PDF 文本可选(非扫描件),扫描件需要先 OCR

### 3. 机动车发票识别不到 VIN 码

- 当前实现识别 `LFM` 开头的 17 位 VIN 码,如发票中 VIN 前缀不同,需修改 [invoice_extractor.py](invoice_extractor.py#L239) 和 [invoice_extractor.py](invoice_extractor.py#L284) 中的正则

### 4. 中文乱码(CSV 输出)

- 已使用 `utf-8-sig` 编码输出,Excel 打开正常显示中文

### 5. Web 模式目录浏览器显示「路径不在允许的白名单内」

- 在 [web_app.py](web_app.py#L25-L31) 的 `ALLOWED_ROOTS` 中添加目标路径
- 例如想访问 `\\server\share`,取消注释那行或新增一行:`r'\\\\server\\share'`

### 6. Web 模式访问服务器共享盘报错

- Web 后端运行账号需有 UNC 路径读权限
- 用 `runas /user:domain\user` 启动,或把 web_app.py 部署为 Windows 服务以有权限账号运行

## 打包发布

使用 PyInstaller 打包为独立可执行文件:

```bash
# 打包 GUI 程序(单文件、无控制台窗口)
pyinstaller --noconsole --onefile gui.py

# 打包命令行程序
pyinstaller --onefile main.py
```

打包后 `dist/` 目录下生成对应 `.exe`,可直接分发给无 Python 环境的用户使用。

> Web 版本不适合用 PyInstaller 打包,建议直接部署在服务器上以服务方式运行。

## 许可证

本项目仅供学习与内部使用。
