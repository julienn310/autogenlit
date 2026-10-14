"""PDF processor for extracting text from annual reports"""

import pdfplumber
from typing import List, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF年报处理器"""

    def __init__(self):
        self.logger = logger

    def extract_text(self, pdf_path: str, max_pages: Optional[int] = None) -> str:
        """
        提取PDF文本内容

        Args:
            pdf_path: PDF文件路径
            max_pages: 最大提取页数，None表示全部提取

        Returns:
            提取的文本内容
        """
        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                pages_to_extract = max_pages if max_pages else total_pages

                self.logger.info(f"PDF总页数: {total_pages}, 将提取前 {pages_to_extract} 页")

                for i, page in enumerate(pdf.pages[:pages_to_extract]):
                    page_text = page.extract_text()
                    if page_text:
                        # 添加页码标记
                        text_parts.append(f"[第{i+1}页]\n{page_text}")

            return "\n\n".join(text_parts)

        except Exception as e:
            self.logger.error(f"PDF文本提取失败: {e}")
            raise

    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
        """
        提取PDF中的表格

        Returns:
            表格列表，每个表格是二维数组
        """
        try:
            all_tables = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
            return all_tables
        except Exception as e:
            self.logger.error(f"PDF表格提取失败: {e}")
            return []

    def extract_financial_notes(self, text: str) -> str:
        """
        从文本中提取财务附注相关内容

        财务附注通常包含在"财务报表附注"、"会计科目附注"、"重要会计政策"等章节

        Args:
            text: 完整PDF文本

        Returns:
            财务附注相关文本
        """
        # 财务附注相关的关键词模式
        patterns = [
            r'财务报表附注[^]*?(?=^(?!.{0,20}附注).*?(?:母公司|合并|注释|科目)|$)',
            r'会计附注[^]*?(?=^(?!.{0,20}附注).*?(?:母公司|合并|注释|科目)|$)',
            r'附\s*注[^]*?(?=^(?!.{0,20}(?:附注|注释)).*?(?:母公司|合并)|$)',
            r'重要会计政策[^]*?(?=^(?!重要).*?(?:母公司|合并)|$)',
            r'债务(?:情况|分析|说明|结构)[^]*?(?=^(?!.{0,20}债务).*?(?:或有|担保)|$)',
            r'负债(?:情况|分析|说明|结构)[^]*?(?=^(?!.{0,20}负债).*?(?:或有|担保)|$)',
            r'借款(?:情况|说明|明细)[^]*?(?=^(?!.{0,20}借款).*?(?:其他|应付)|$)',
            r'关联方(?:交易|说明|披露)[^]*?(?=^(?!.{0,20}关联).*?(?:其他|或有)|$)',
            r'担保(?:情况|说明|披露)[^]*?(?=^(?!.{0,20}担保).*?(?:其他|或有)|$)',
            r'或有负债[^]*?(?=^(?!.{0,20}或有).*?(?:其他|重要)|$)',
        ]

        # 如果找不到精确匹配，提取包含关键词的段落
        lines = text.split('\n')
        relevant_lines = []
        in_section = False
        section_keywords = ['附注', '注释', '会计科目', '重要会计', '借款', '负债', '担保', '或有', '关联方']

        for line in lines:
            # 检查是否进入财务附注相关章节
            if any(kw in line for kw in section_keywords):
                in_section = True

            if in_section:
                relevant_lines.append(line)

                # 如果遇到新的报表标题（不是附注相关的），可能已经离开附注区域
                if any(marker in line for marker in ['合并利润表', '合并现金流量表', '母公司利润表']) and '附注' not in line:
                    if len(relevant_lines) > 100:  # 确保已经收集了足够内容
                        break

        if relevant_lines:
            return '\n'.join(relevant_lines)

        # 回退方案：返回文本中所有包含关键词的行
        fallback_lines = [line for line in lines if any(kw in line for kw in section_keywords)]
        return '\n'.join(fallback_lines[:200])  # 限制返回量

    def chunk_text(self, text: str, chunk_size: int = 6000, overlap: int = 200) -> List[str]:
        """
        将长文本分块以适应LLM上下文限制

        Args:
            text: 输入文本
            chunk_size: 每块最大字符数
            overlap: 块之间的重叠字符数

        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 尝试在句号、逗号或换行处断点，避免在单词中间截断
            if end < len(text):
                # 寻找最后一个句号或换行
                break_chars = ['\n', '。', '，', '；', '：', '.']
                for char in break_chars:
                    last_pos = text.rfind(char, start + chunk_size - 200, end)
                    if last_pos > start + chunk_size - 500:
                        end = last_pos + 1
                        break

            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks

    def extract_debt_related_content(self, text: str) -> str:
        """
        专门提取债务相关内容（短期借款、长期借款、应付债券等）

        Args:
            text: PDF文本

        Returns:
            债务相关文本
        """
        debt_keywords = [
            '短期借款', '长期借款', '应付债券', '应付票据',
            '一年内到期非流动负债', '租赁负债', '长期应付款',
            '带息负债', '金融负债', '股东权益', '负债合计',
            '资产总计', '流动负债', '非流动负债'
        ]

        lines = text.split('\n')
        relevant = []

        for i, line in enumerate(lines):
            if any(kw in line for kw in debt_keywords):
                # 提取该行以及上下文
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                context = lines[start:end]
                relevant.extend(context)

        return '\n'.join(relevant[:300])  # 限制长度