"""发票信息批量提取工具 - Web 版本 (Flask + SSE)"""

import os
import json
import uuid
import threading
import queue
from datetime import datetime

from flask import (Flask, request, render_template, jsonify,
                   send_file, Response)
from invoice_extractor import InvoiceExtractor
from exporter import write_to_excel

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB 上传上限

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 目录浏览白名单 — 只允许浏览这些根目录下的子目录
# 根据实际需求修改或追加(如服务器共享盘 UNC 路径)
ALLOWED_ROOTS = [
    r'D:\\',
    r'E:\\',
    # r'\\\\server\\share',  # 示例:UNC 共享盘
    os.path.expanduser('~'),
]

# 内存任务表(单机够用,无需 Redis)
TASKS = {}


class TaskState:
    """单个提取任务的状态容器"""

    def __init__(self):
        self.events = queue.Queue()
        self.progress = 0
        self.output_path = None
        self.finished = False
        self.error = None


def _failed_row(filename):
    """构造失败占位行"""
    return {
        '文件名': filename, '发票号码': '提取失败',
        '发票代码': '提取失败', '开票日期': '提取失败',
        '销售方': '提取失败', '销售方税号': '提取失败',
        '购买方': '提取失败', '购买方税号': '提取失败',
        '商品名称': '提取失败', '规格型号': '提取失败',
        '单位': '提取失败', '数量': '提取失败',
        '单价': '提取失败', '金额': '提取失败',
        '税率': '提取失败', '税额': '提取失败',
        '价税合计': '提取失败', '车辆识别代号/车架号码': '提取失败',
    }


def process_task(task_id, pdf_paths):
    """后台工作线程:逐文件提取,通过队列推送进度"""
    state = TASKS[task_id]
    results = []
    total = len(pdf_paths)
    try:
        for i, pdf_path in enumerate(pdf_paths):
            filename = os.path.basename(pdf_path)
            state.events.put({'type': 'log', 'msg': f'正在处理: {filename}'})
            try:
                extractor = InvoiceExtractor(pdf_path)
                rows = extractor.extract_all_rows()
                for row in rows:
                    row['文件名'] = filename
                    results.append(row)
                state.events.put({
                    'type': 'log',
                    'msg': f'  ✓ 提取成功 ({len(rows)}行)'
                })
            except Exception as e:
                state.events.put({
                    'type': 'log',
                    'msg': f'  ✗ 处理失败: {str(e)}'
                })
                results.append(_failed_row(filename))

            state.progress = int((i + 1) / total * 100)
            state.events.put({'type': 'progress', 'value': state.progress})

        # 生成 Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(OUTPUT_DIR, f'发票信息_{timestamp}.xlsx')
        write_to_excel(results, output_path)
        state.output_path = output_path
        state.events.put({
            'type': 'done',
            'output': os.path.basename(output_path)
        })
    except Exception as e:
        state.error = str(e)
        state.events.put({'type': 'error', 'msg': str(e)})
    finally:
        state.finished = True


def _scan_pdfs(dir_path):
    """递归扫描目录下所有 PDF"""
    pdf_files = []
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, f))
    return pdf_files


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/browse', methods=['POST'])
def browse_directory():
    """列出指定目录下的子目录(用于前端目录选择器)
    不传 path 时返回白名单根目录列表。"""
    data = request.get_json() or {}
    dir_path = data.get('path', '').strip()

    # 不传路径:返回白名单根目录
    if not dir_path:
        roots = []
        for r in ALLOWED_ROOTS:
            if os.path.isdir(r):
                roots.append({'name': r, 'path': r})
        return jsonify({'current': '', 'parent': '', 'dirs': roots})

    # 传入路径:校验是否在白名单内(防目录穿越)
    norm = os.path.normpath(dir_path)
    allowed = any(
        norm == os.path.normpath(r) or norm.startswith(
            os.path.normpath(r) + os.sep
        )
        for r in ALLOWED_ROOTS
    )
    if not allowed:
        return jsonify({'error': f'路径不在允许的白名单内:{dir_path}'}), 403
    if not os.path.isdir(norm):
        return jsonify({'error': '路径不是有效目录'}), 400

    # 列出子目录
    subdirs = []
    try:
        for entry in os.listdir(norm):
            full = os.path.join(norm, entry)
            if os.path.isdir(full):
                subdirs.append({'name': entry, 'path': full})
    except PermissionError:
        return jsonify({'error': '无权限访问该目录'}), 403

    # 计算父目录(若到达白名单根,则 parent 为空表示返回根列表)
    parent = ''
    for r in ALLOWED_ROOTS:
        rn = os.path.normpath(r)
        if norm == rn:
            parent = ''  # 已是根,返回到根列表
            break
        if norm.startswith(rn + os.sep):
            parent = os.path.dirname(norm)
            break

    return jsonify({'current': norm, 'parent': parent, 'dirs': subdirs})


@app.route('/scan', methods=['POST'])
def scan_directory():
    """扫描目录,返回 PDF 清单(不启动处理)"""
    data = request.get_json() or {}
    dir_path = data.get('path', '').strip()
    if not dir_path or not os.path.isdir(dir_path):
        return jsonify({'error': '路径无效或不是目录'}), 400
    pdf_files = _scan_pdfs(dir_path)
    return jsonify({'files': pdf_files, 'count': len(pdf_files)})


@app.route('/process-path', methods=['POST'])
def process_path():
    """按目录路径启动处理(支持 UNC 共享盘)"""
    data = request.get_json() or {}
    dir_path = data.get('path', '').strip()
    if not dir_path or not os.path.isdir(dir_path):
        return jsonify({'error': '路径无效或不是目录'}), 400
    pdf_files = _scan_pdfs(dir_path)
    if not pdf_files:
        return jsonify({'error': '目录下未发现PDF文件'}), 400
    task_id = uuid.uuid4().hex
    TASKS[task_id] = TaskState()
    threading.Thread(
        target=process_task, args=(task_id, pdf_files), daemon=True
    ).start()
    return jsonify({'task_id': task_id, 'count': len(pdf_files)})


@app.route('/upload', methods=['POST'])
def upload():
    """接收多文件上传并启动处理"""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': '未上传文件'}), 400
    saved = []
    for f in files:
        if f and f.filename and f.filename.lower().endswith('.pdf'):
            path = os.path.join(
                UPLOAD_DIR, f"{uuid.uuid4().hex}_{f.filename}"
            )
            f.save(path)
            saved.append(path)
    if not saved:
        return jsonify({'error': '未发现PDF文件'}), 400
    task_id = uuid.uuid4().hex
    TASKS[task_id] = TaskState()
    threading.Thread(
        target=process_task, args=(task_id, saved), daemon=True
    ).start()
    return jsonify({'task_id': task_id})


@app.route('/progress/<task_id>')
def progress(task_id):
    """SSE 流:实时推送 log/progress/done/error 事件"""
    def stream():
        state = TASKS.get(task_id)
        if not state:
            yield 'event: error\ndata: {"msg":"任务不存在"}\n\n'
            return
        while True:
            try:
                evt = state.events.get(timeout=30)
                yield (
                    f"event: {evt['type']}\n"
                    f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                )
                if evt['type'] in ('done', 'error'):
                    break
            except queue.Empty:
                if state.finished:
                    break
                yield ': ping\n\n'
    return Response(
        stream(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@app.route('/download/<filename>')
def download(filename):
    """下载生成的 Excel"""
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.exists(path):
        return jsonify({'error': '文件不存在'}), 404
    return send_file(path, as_attachment=True, download_name=safe)


if __name__ == '__main__':
    # threaded=True 允许多请求并发(含 SSE 长连接)
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
