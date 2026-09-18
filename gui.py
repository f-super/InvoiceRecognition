#!/usr/bin/env python3
"""发票信息批量提取工具 - GUI版本"""

import os
import sys
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QProgressBar,
                             QFileDialog, QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class WorkerThread(QThread):
    """工作线程 - 处理发票提取"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, input_paths, output_dir):
        super().__init__()
        self.input_paths = input_paths
        self.output_dir = output_dir

    def run(self):
        try:
            import openpyxl
            from invoice_extractor import InvoiceExtractor

            results = []
            total = len(self.input_paths)
            
            for i, pdf_path in enumerate(self.input_paths):
                filename = os.path.basename(pdf_path)
                self.log.emit(f"正在处理: {filename}")
                
                try:
                    extractor = InvoiceExtractor(pdf_path)
                    rows = extractor.extract_all_rows()
                    
                    for row in rows:
                        row['文件名'] = filename
                        results.append(row)
                    
                    self.log.emit(f"  ✓ 提取成功 ({len(rows)}行)")
                except Exception as e:
                    self.log.emit(f"  ✗ 处理失败: {str(e)}")
                    results.append({
                        '文件名': filename,
                        '发票号码': '提取失败',
                        '发票代码': '提取失败',
                        '开票日期': '提取失败',
                        '销售方': '提取失败',
                        '销售方税号': '提取失败',
                        '购买方': '提取失败',
                        '购买方税号': '提取失败',
                        '商品名称': '提取失败',
                        '规格型号': '提取失败',
                        '单位': '提取失败',
                        '数量': '提取失败',
                        '单价': '提取失败',
                        '金额': '提取失败',
                        '税率': '提取失败',
                        '税额': '提取失败',
                        '价税合计': '提取失败',
                        '车辆识别代号/车架号码': '提取失败',
                    })
                
                self.progress.emit(int((i + 1) / total * 100))

            # 写入Excel
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f'发票信息_{timestamp}.xlsx')
            
            headers = ['文件名', '发票号码', '发票代码', '开票日期', '销售方', '销售方税号',
                       '购买方', '购买方税号', '商品名称', '规格型号', '单位', '数量',
                       '单价', '金额', '税率', '税额', '价税合计', '车辆识别代号/车架号码']

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = '发票信息'
            ws.append(headers)

            for row_data in results:
                ws.append([row_data.get(h, '') for h in headers])

            wb.save(output_path)
            self.finished.emit(output_path)
            
        except Exception as e:
            self.log.emit(f"错误: {str(e)}")
            self.finished.emit("")


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('发票信息批量提取工具')
        self.setGeometry(100, 100, 600, 400)
        
        self.input_paths = []
        self.output_dir = os.path.expanduser('~')
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel('发票信息批量提取工具')
        title_label.setStyleSheet('font-size: 18px; font-weight: bold; color: #333;')
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 状态显示
        self.status_label = QLabel('请选择PDF文件或文件夹')
        self.status_label.setStyleSheet('color: #666;')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 选择文件按钮
        self.select_button = QPushButton('选择文件/文件夹')
        self.select_button.setStyleSheet('''
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        ''')
        self.select_button.clicked.connect(self.select_files)
        button_layout.addWidget(self.select_button)
        
        # 打开输出目录按钮
        self.output_button = QPushButton('打开输出目录')
        self.output_button.setStyleSheet('''
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        ''')
        self.output_button.clicked.connect(self.open_output_dir)
        self.output_button.setEnabled(False)
        button_layout.addWidget(self.output_button)
        
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet('background-color: #f5f5f5;')
        layout.addWidget(self.log_text)
        
        # 处理按钮
        self.process_button = QPushButton('开始提取')
        self.process_button.setStyleSheet('''
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 14px 28px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        ''')
        self.process_button.clicked.connect(self.start_process)
        self.process_button.setEnabled(False)
        layout.addWidget(self.process_button)
        
        central_widget.setLayout(layout)

    def select_files(self):
        """选择文件或文件夹"""
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.setNameFilter('PDF文件 (*.pdf)')
        
        # 也允许选择文件夹
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        
        if dialog.exec_():
            selected = dialog.selectedFiles()
            
            # 检查是否选择了文件夹
            folders = [f for f in selected if os.path.isdir(f)]
            files = [f for f in selected if os.path.isfile(f) and f.lower().endswith('.pdf')]
            
            # 如果选择了文件夹，获取其中的PDF文件
            for folder in folders:
                for filename in os.listdir(folder):
                    if filename.lower().endswith('.pdf'):
                        files.append(os.path.join(folder, filename))
            
            self.input_paths = files
            self.output_dir = os.path.dirname(files[0]) if files else os.path.expanduser('~')
            
            if self.input_paths:
                self.status_label.setText(f'已选择 {len(self.input_paths)} 个文件')
                self.process_button.setEnabled(True)
                self.output_button.setEnabled(True)
                self.log_text.clear()
                for f in self.input_paths:
                    self.log_text.append(f'• {os.path.basename(f)}')
            else:
                self.status_label.setText('未选择任何PDF文件')
                self.process_button.setEnabled(False)

    def start_process(self):
        """开始处理"""
        self.select_button.setEnabled(False)
        self.process_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self.worker = WorkerThread(self.input_paths, self.output_dir)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_finished)
        self.worker.log.connect(self.add_log)
        self.worker.start()

    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)

    def add_log(self, text):
        """添加日志"""
        self.log_text.append(text)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def process_finished(self, output_path):
        """处理完成"""
        self.select_button.setEnabled(True)
        self.process_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if output_path:
            self.log_text.append(f'\n处理完成！结果已保存到:\n{output_path}')
            QMessageBox.information(self, '成功', f'处理完成！\n\n结果已保存到:\n{output_path}')
        else:
            QMessageBox.critical(self, '错误', '处理过程中发生错误')

    def open_output_dir(self):
        """打开输出目录"""
        if os.path.exists(self.output_dir):
            if sys.platform == 'win32':
                os.startfile(self.output_dir)
            else:
                subprocess.run(['xdg-open', self.output_dir])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())