"""发票信息提取器 - 适配电子发票格式"""

import re
import pdfplumber
from decimal import Decimal, ROUND_HALF_UP


class InvoiceExtractor:
    """发票信息提取器 - 支持增值税电子发票"""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.text = self._extract_text()
        self.tables = self._extract_tables()

    def _extract_text(self):
        """提取PDF中的所有文本"""
        text = ""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"pdfplumber提取失败: {e}")
        return text

    def _extract_tables(self):
        """提取PDF中的表格"""
        tables = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
        except Exception as e:
            print(f"表格提取失败: {e}")
        return tables

    def extract_invoice_number(self):
        """提取发票号码"""
        patterns = [
            r'发票号码[：:]?\s*([0-9]{16,20})',
            r'发票号码[：:]?\s*([A-Z0-9]{8,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                return match.group(1).strip()
        return ""

    def extract_invoice_code(self):
        """提取发票代码 - 机动车发票可能没有单独的发票代码"""
        patterns = [
            r'发票代码[：:]?\s*([0-9]{10,12})',
            r'代码[：:]?\s*([0-9]{10,12})',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                return match.group(1).strip()
        return ""

    def extract_invoice_date(self):
        """提取开票日期"""
        patterns = [
            r'开票日期[：:]?\s*(\d{4}年\d{1,2}月\d{1,2}日)',
            r'开票日期[：:]?\s*(\d{4}-\d{1,2}-\d{1,2})',
            r'开票日期[：:]?\s*(\d{4}\.\d{1,2}\.\d{1,2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                result = match.group(1).strip()
                result = result.replace('年', '-').replace('月', '-').replace('日', '')
                return result
        return ""

    def extract_seller(self):
        """提取销售方信息"""
        lines = self.text.split('\n')
        for line in lines:
            # 查找"销 名称"行（销售方在右侧）
            if '销 名称' in line:
                # 提取"销 名称："后面的公司名称
                match = re.search(r'销 名称[：:]?\s*([^\s\n，,，]+(?:有限公司|公司))', line)
                if match:
                    return match.group(1).strip()

        # 从表格中查找
        for table in self.tables:
            for row in table:
                if row:
                    row_str = ' '.join([str(cell) for cell in row if cell])
                    if '销 名称' in row_str:
                        for cell in row:
                            if cell and isinstance(cell, str) and '惠州' in cell:
                                match = re.search(r'([^\n，,]+有限公司|[^\n，,]+公司)', cell)
                                if match:
                                    return match.group(1).strip()
        return ""

    def extract_seller_tax_id(self):
        """提取销售方纳税人识别号"""
        lines = self.text.split('\n')
        for line in lines:
            # 销售方税号在右侧
            if '销' in line and ('统一社会信用代码' in line or '纳税人识别号' in line):
                # 提取最后一个税号（销售方在右侧）
                matches = re.findall(r'(91[0-9A-Z]{15})', line)
                if matches:
                    return matches[-1].strip()  # 返回最后一个（销售方）

        # 从表格中查找
        for table in self.tables:
            for row in table:
                if row:
                    row_str = ' '.join([str(cell) for cell in row if cell])
                    if '销' in row_str and '9144' in row_str:
                        matches = re.findall(r'(91[0-9A-Z]{15})', row_str)
                        if matches:
                            return matches[-1].strip()
        return ""

    def extract_buyer(self):
        """提取购买方信息"""
        lines = self.text.split('\n')
        for line in lines:
            # 查找"购 名称"行（购买方在左侧）
            if '购 名称' in line:
                match = re.search(r'购 名称[：:]?\s*([^\s\n，,，]+(?:有限公司|公司))', line)
                if match:
                    return match.group(1).strip()

        # 从表格中查找
        for table in self.tables:
            for row in table:
                if row:
                    row_str = ' '.join([str(cell) for cell in row if cell])
                    if '购 名称' in row_str:
                        for cell in row:
                            if cell and isinstance(cell, str) and '厦门' in cell:
                                match = re.search(r'([^\n，,]+有限公司|[^\n，,]+公司)', cell)
                                if match:
                                    return match.group(1).strip()
        return ""

    def extract_buyer_tax_id(self):
        """提取购买方纳税人识别号"""
        lines = self.text.split('\n')
        for line in lines:
            # 购买方税号在左侧
            if '购' in line and ('统一社会信用代码' in line or '纳税人识别号' in line):
                matches = re.findall(r'(91[0-9A-Z]{15})', line)
                if matches:
                    return matches[0].strip()  # 返回第一个（购买方）

        # 从表格中查找
        for table in self.tables:
            for row in table:
                if row:
                    row_str = ' '.join([str(cell) for cell in row if cell])
                    if '购' in row_str and '9135' in row_str:
                        matches = re.findall(r'(91[0-9A-Z]{15})', row_str)
                        if matches:
                            return matches[0].strip()
        return ""

    def extract_buyer_tax_id(self):
        """提取购买方纳税人识别号"""
        lines = self.text.split('\n')
        for line in lines:
            # 购买方税号在左侧
            if '购' in line and ('统一社会信用代码' in line or '纳税人识别号' in line):
                matches = re.findall(r'(91[0-9A-Z]{15})', line)
                if matches:
                    return matches[0].strip()  # 返回第一个（购买方 车辆识别代号/车架号码）

        # 从表格中查找
        for table in self.tables:
            for row in table:
                if row:
                    row_str = ' '.join([str(cell) for cell in row if cell])
                    if '购' in row_str and '9135' in row_str:
                        matches = re.findall(r'(91[0-9A-Z]{15})', row_str)
                        if matches:
                            return matches[0].strip()
        return ""

    def extract_tax_rate(self):
        """提取税率"""
        match = re.search(r'税率/征收率\s*(\d+%)', self.text)
        if match:
            return match.group(1).strip()
        
        match = re.search(r'(\d+%)\s*税额', self.text)
        if match:
            return match.group(1).strip()
        
        # 如果没找到，返回常见税率
        return "13%"

    def _parse_number(self, text):
        """解析数字字符串"""
        if not text:
            return Decimal('0')
        text = str(text).replace(',', '').replace(' ', '').replace('￥', '').replace('¥', '')
        try:
            return Decimal(text)
        except:
            return Decimal('0')

    def _format_number(self, value, decimals=2):
        """格式化数字"""
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def extract_items_from_text(self):
        """从文本中提取商品明细"""
        items = []
        lines = self.text.split('\n')
        
        # 查找表头行之后的数据行
        header_found = False
        for i, line in enumerate(lines):
            if '项目名称' in line and '车辆识别代号' in line:
                header_found = True
                continue
            
            if header_found and line.strip():
                # 跳过合计行
                if '合计' in line or '价税合计' in line:
                    continue
                
                # 匹配商品行：包含车架号格式 (LFM开头的17位VIN码)
                vin_match = re.search(r'(LFM[A-Z0-9]{14})', line)
                if vin_match:
                    vin = vin_match.group(1)
                    
                    # 提取金额信息
                    numbers = re.findall(r'[\d,]+\.?\d*', line)
                    
                    # 通常格式: 单价 金额 税率 税额
                    unit_price = numbers[-4] if len(numbers) >= 4 else '0'
                    amount = numbers[-3] if len(numbers) >= 3 else '0'
                    tax_amount = numbers[-1] if len(numbers) >= 1 else '0'
                    
                    # 提取商品名称
                    name_match = re.search(r'\*机动车\*(.*?)\s+LFM', line)
                    name = name_match.group(1).strip() if name_match else '机动车'
                    
                    items.append({
                        '商品名称': name,
                        '规格型号': '',
                        '单位': '辆',
                        '数量': '1',
                        '单价': unit_price,
                        '金额': amount,
                        '税额': tax_amount,
                        '车架号': vin,
                    })
        
        return items

    def extract_items_from_tables(self):
        """从表格中提取商品明细"""
        items = []
        
        for table in self.tables:
            for row in table:
                if row and len(row) > 0:
                    row_str = str(row[0]) if row[0] else ''
                    
                    # 查找包含商品数据的行
                    if '*机动车*' in row_str or 'LFM' in row_str:
                        # 分割数据
                        parts = row_str.split('\n')
                        for part in parts:
                            if '*机动车*' in part and 'LFM' in part:
                                # 提取车架号
                                vin_match = re.search(r'(LFM[A-Z0-9]{14})', part)
                                if vin_match:
                                    vin = vin_match.group(1)
                                    
                                    # 提取金额
                                    numbers = re.findall(r'[\d,]+\.?\d*', part)
                                    unit_price = numbers[-4] if len(numbers) >= 4 else '0'
                                    amount = numbers[-3] if len(numbers) >= 3 else '0'
                                    tax_amount = numbers[-1] if len(numbers) >= 1 else '0'
                                    
                                    # 提取商品名称
                                    name_match = re.search(r'\*机动车\*(.*?)\s+LFM', part)
                                    name = name_match.group(1).strip() if name_match else '机动车'
                                    
                                    items.append({
                                        '商品名称': name,
                                        '规格型号': '',
                                        '单位': '辆',
                                        '数量': '1',
                                        '单价': unit_price,
                                        '金额': amount,
                                        '税额': tax_amount,
                                        '车架号': vin,
                                    })
        
        return items

    def calculate_item_prices(self, items, tax_rate_str):
        """计算每行商品的不含税金额、税额和价税合计"""
        tax_rate = Decimal('0')
        if tax_rate_str:
            rate_str = tax_rate_str.replace('%', '').strip()
            try:
                tax_rate = Decimal(rate_str) / Decimal('100')
            except:
                tax_rate = Decimal('0.13')

        for item in items:
            amount = self._parse_number(item.get('金额', '0'))
            
            # 如果已经有税额，直接使用
            if '税额' in item and item['税额']:
                tax_amount = self._parse_number(item['税额'])
                price_excluding_tax = amount - tax_amount
            else:
                if tax_rate > 0:
                    price_excluding_tax = amount / (Decimal('1') + tax_rate)
                    tax_amount = amount - price_excluding_tax
                else:
                    price_excluding_tax = amount
                    tax_amount = Decimal('0')

            total_with_tax = amount + tax_amount

            item['税额'] = self._format_number(tax_amount)
            item['价税合计'] = self._format_number(total_with_tax)

        return items

    def extract_all_rows(self):
        """提取所有行，每行商品单独一条记录"""
        invoice_info = self.extract_invoice_info()
        tax_rate = self.extract_tax_rate()

        # 优先从文本提取商品（更准确）
        items = self.extract_items_from_text()
        
        # 如果文本提取不到，尝试从表格提取
        if not items:
            items = self.extract_items_from_tables()

        # 计算价格
        items = self.calculate_item_prices(items, tax_rate)

        # 生成所有行
        rows = []
        for item in items:
            row = {
                '文件名': '',
                '发票号码': invoice_info['发票号码'],
                '发票代码': invoice_info['发票代码'],
                '开票日期': invoice_info['开票日期'],
                '销售方': invoice_info['销售方'],
                '销售方税号': invoice_info['销售方税号'],
                '购买方': invoice_info['购买方'],
                '购买方税号': invoice_info['购买方税号'],
                '商品名称': item.get('商品名称', ''),
                '规格型号': item.get('规格型号', ''),
                '单位': item.get('单位', ''),
                '数量': item.get('数量', ''),
                '单价': item.get('单价', ''),
                '金额': item.get('金额', ''),
                '税率': item.get('税率', tax_rate),
                '税额': item.get('税额', 0),
                '价税合计': item.get('价税合计', 0),
                '车辆识别代号/车架号码': item.get('车架号', ''),
            }
            rows.append(row)

        # 如果没有提取到任何商品，生成一条空行
        if not rows:
            rows.append({
                '文件名': '',
                '发票号码': invoice_info['发票号码'],
                '发票代码': invoice_info['发票代码'],
                '开票日期': invoice_info['开票日期'],
                '销售方': invoice_info['销售方'],
                '销售方税号': invoice_info['销售方税号'],
                '购买方': invoice_info['购买方'],
                '购买方税号': invoice_info['购买方税号'],
                '商品名称': '',
                '规格型号': '',
                '单位': '',
                '数量': '',
                '单价': '',
                '金额': '',
                '税率': tax_rate,
                '税额': 0,
                '价税合计': 0,
                '车辆识别代号/车架号码': '',
            })

        return rows

    def extract_invoice_info(self):
        """提取发票基本信息"""
        return {
            '发票号码': self.extract_invoice_number(),
            '发票代码': self.extract_invoice_code(),
            '开票日期': self.extract_invoice_date(),
            '销售方': self.extract_seller(),
            '销售方税号': self.extract_seller_tax_id(),
            '购买方': self.extract_buyer(),
            '购买方税号': self.extract_buyer_tax_id(),
        }

    def extract_info(self):
        """提取所有发票信息（兼容旧接口）"""
        rows = self.extract_all_rows()
        if rows:
            return rows[0]
        return self.extract_invoice_info()