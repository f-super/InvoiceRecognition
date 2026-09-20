const $ = id => document.getElementById(id);

function log(msg, level = 'info') {
    const colors = {
        info: '#ecf0f1', success: '#2ecc71',
        error: '#e74c3c', warn: '#f39c12'
    };
    const div = document.createElement('div');
    div.style.color = colors[level] || colors.info;
    div.textContent = msg;
    $('logArea').appendChild(div);
    $('logArea').scrollTop = $('logArea').scrollHeight;
}

function setProgress(v) {
    $('progressBar').style.width = v + '%';
    $('progressBar').textContent = v + '%';
}

// ===== 目录浏览器逻辑 =====
// 状态:当前路径 currentPath,扫描缓存 scanCache
let currentPath = '';
let scanCache = null;

async function browse(path = '') {
    // 调 /browse 拿子目录列表
    const res = await fetch('/browse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    });
    const data = await res.json();
    if (data.error) {
        $('dirList').innerHTML = `<div class="text-danger">✗ ${data.error}</div>`;
        return;
    }
    renderBreadcrumb(data.current || path, data.parent);
    renderDirList(data.dirs, data.current || path);
    currentPath = data.current || path;
    // 浏览新目录时清空扫描缓存
    if (scanCache && scanCache.__path !== currentPath) {
        scanCache = null;
        $('scanResult').innerHTML = '';
        $('processPathBtn').disabled = true;
    }
}

function renderBreadcrumb(current, parent) {
    const bc = $('breadcrumb');
    if (!current) {
        bc.innerHTML = '<span class="text-muted">选择根目录:</span>';
        return;
    }
    const parts = current.split(/[\\/]/).filter(Boolean);
    let html = '<button class="btn btn-sm btn-link p-0 text-primary" data-path="">根目录</button>';
    let acc = '';
    for (let i = 0; i < parts.length; i++) {
        acc = (acc ? acc + '\\' : '') + parts[i];
        const full = i === 0 ? parts[i] : acc;
        html += `<span class="text-muted mx-1">/</span>`;
        html += `<button class="btn btn-sm btn-link p-0 ${i === parts.length - 1 ? 'fw-bold' : 'text-primary'}" data-path="${full}">${parts[i]}</button>`;
    }
    bc.innerHTML = html;
    bc.querySelectorAll('button[data-path]').forEach(btn => {
        btn.onclick = () => browse(btn.dataset.path);
    });
}

function renderDirList(dirs, current) {
    const list = $('dirList');
    if (!dirs || dirs.length === 0) {
        list.innerHTML = '<div class="text-muted small">该目录下无子目录。可点击下方「扫描此路径」检查 PDF。</div>';
        return;
    }
    list.innerHTML = dirs.map(d =>
        `<div class="dir-item p-2 rounded" style="cursor:pointer;" data-path="${d.path}">
            <span class="me-2">📁</span>${d.name}
        </div>`
    ).join('');
    list.querySelectorAll('.dir-item').forEach(item => {
        item.onclick = () => browse(item.dataset.path);
        item.onmouseenter = () => item.style.background = '#e9ecef';
        item.onmouseleave = () => item.style.background = '';
    });
}

// 首次加载时浏览根目录列表
browse('');

// 点击「扫描此路径」按钮 — 使用手输路径或当前浏览路径
$('scanBtn').onclick = async () => {
    const path = $('dirPath').value.trim() || currentPath;
    if (!path) return alert('请先进入一个目录,或手动输入路径');
    const res = await fetch('/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    });
    const data = await res.json();
    if (data.error) {
        $('scanResult').innerHTML = `<div class="text-danger">✗ ${data.error}</div>`;
        $('processPathBtn').disabled = true;
        return;
    }
    scanCache = { ...data, __path: path };
    window.__scanPath = path;
    $('scanResult').innerHTML =
        `<div class="text-success">✓ 目录有效,共发现 ${data.count} 个PDF</div>` +
        (data.count > 0
            ? data.files.map(f => `<div class="small">• ${f}</div>`).join('')
            : '<div class="text-muted small">该目录下没有PDF文件</div>');
    $('processPathBtn').disabled = data.count === 0;
};

// 按路径处理
$('processPathBtn').onclick = async () => {
    const res = await fetch('/process-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: window.__scanPath })
    });
    const data = await res.json();
    if (data.error) return alert(data.error);
    log(`开始处理 ${data.count} 个文件`, 'info');
    startSSE(data.task_id);
};

// 上传文件列表展示
$('fileInput').onchange = () => {
    const files = [...$('fileInput').files];
    $('uploadList').innerHTML =
        files.map(f => `<div class="small">• ${f.name}</div>`).join('');
    $('uploadBtn').disabled = files.length === 0;
};

// 上传并处理
$('uploadBtn').onclick = async () => {
    const fd = new FormData();
    [...$('fileInput').files].forEach(f => fd.append('files', f));
    const res = await fetch('/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) return alert(data.error);
    log(`开始处理 ${$('fileInput').files.length} 个文件`, 'info');
    startSSE(data.task_id);
};

// SSE 接收进度
function startSSE(taskId) {
    $('progressBar').style.width = '0%';
    $('progressBar').textContent = '0%';
    $('logArea').innerHTML = '';
    $('downloadArea').innerHTML = '';

    const es = new EventSource(`/progress/${taskId}`);

    es.addEventListener('log', e => {
        const d = JSON.parse(e.data);
        const level = d.msg.includes('✓') ? 'success'
            : (d.msg.includes('✗') ? 'error' : 'info');
        log(d.msg, level);
    });

    es.addEventListener('progress', e => {
        setProgress(JSON.parse(e.data).value);
    });

    es.addEventListener('done', e => {
        const d = JSON.parse(e.data);
        setProgress(100);
        log('处理完成!', 'success');
        $('downloadArea').innerHTML =
            `<a href="/download/${d.output}" class="btn btn-primary btn-lg">下载 Excel: ${d.output}</a>`;
        es.close();
    });

    es.addEventListener('error', e => {
        try {
            const d = JSON.parse(e.data);
            log('错误: ' + d.msg, 'error');
        } catch (_) {
            log('连接中断', 'warn');
        }
        es.close();
    });
}
