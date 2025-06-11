from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import jsonschema
import spacy
import networkx as nx
from nltk import edit_distance
from collections import defaultdict

# 加载中文模型
try:
    nlp = spacy.load("zh_core_web_trf")
except OSError:
    print("警告：未安装 zh_core_web_trf，自动降级为 zh_core_web_sm，部分相似度功能不准确。建议运行 python -m spacy download zh_core_web_trf 安装大模型。")
    nlp = spacy.load("zh_core_web_sm")

@dataclass
class ContentBlock:
    """内容块数据类"""
    content: str
    title: str
    related_sections: List[str] = field(default_factory=list)
    similarity_scores: Dict[str, float] = None


class Prompts:
    """
    投标文件生成提示词管理类
    
    该类包含用于生成投标文件大纲和内容的提示词模板。
    所有提示词都使用中文，以确保与目标使用场景一致。
    """

    # JSON验证模式
    OUTLINE_SCHEMA = {
        "type": "object",
        "required": ["body_paragraphs"],
        "properties": {
            "body_paragraphs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["chapter_title", "sections"],
                    "properties": {
                        "chapter_title": {"type": "string"},
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["section_title", "sub_sections"],
                                "properties": {
                                    "section_title": {"type": "string"},
                                    "sub_sections": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["sub_section_title", "content_summary"],
                                            "properties": {
                                                "sub_section_title": {"type": "string"},
                                                "content_summary": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    # 1. 大纲生成相关提示词
    OUTLINE_SYSTEM_ROLE = """你是投标文件编制专家。你的任务是根据技术要求和评分标准，生成一份测试版的投标文件大纲，只需要1个章节，每个章节包含一个节，每个节包含一个子节。
你需要确保：
1. 所有回复必须是标准的 JSON 格式
2. 大纲结构完整，包含章、节、子节三级标题
3. 一级标题与评分标准对应
4. 涵盖所有技术要求
5. 三级标题下有详细的内容边界描述

输出格式必须严格遵循：
{
    "body_paragraphs": [
        {
            "chapter_title": "第一章 xxx",
            "sections": [
                {
                    "section_title": "1.1 xxx",
                    "sub_sections": [
                        {
                            "sub_section_title": "1.1.1 xxx",
                            "content_summary": "xxx"
                        }
                    ]
                }
            ]
        }
    ]
}"""

    OUTLINE_TECH_USER = """这是项目的技术要求，请仔细阅读并记住这些要求：

【技术要求】
{tech_content}"""

    @classmethod
    def validate_outline(cls, outline: str) -> bool:
        """
        验证大纲 JSON 格式是否正确
        
        Args:
            outline: 大纲 JSON 字符串
            
        Returns:
            bool: 格式是否正确
            
        Raises:
            ValueError: 如果 JSON 格式错误
        """
        try:
            data = json.loads(outline)
            jsonschema.validate(instance=data, schema=cls.OUTLINE_SCHEMA)
            return True
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            raise ValueError(f"大纲格式验证失败: {str(e)}")

    @classmethod
    def generate_outline_prompt(cls, tech_content: str, score_content: str) -> Dict[str, str]:
        """
        生成大纲生成提示词
        
        Args:
            tech_content: 技术要求内容
            score_content: 评分标准内容
            
        Returns:
            dict: 包含系统角色和用户指令的提示词字典
        """
        if not tech_content or not score_content:
            raise ValueError("技术要求和评分标准不能为空")
            
        return {
            "system_role": cls.OUTLINE_SYSTEM_ROLE,
            "tech_prompt": cls.OUTLINE_TECH_USER.format(tech_content=tech_content),
            "score_prompt": cls.OUTLINE_SCORE_USER.format(score_content=score_content),
            "generate_prompt": cls.OUTLINE_GENERATE_USER
        }

    OUTLINE_SCORE_USER = """这是项目的评分标准，请仔细阅读并记住这些标准：

【评分标准】
{score_content}"""

    OUTLINE_GENERATE_USER = """现在请基于之前提供的技术要求和评分标准，生成一份完整的投标文件大纲。要求：
1. 确保大纲结构完整
2. 确保一级标题与评分标准对应
3. 确保涵盖所有技术要求
4. 确保三级标题下有详细的内容边界描述
5. 直接返回完整的 JSON，不要有任何其他文字
6. 确保 JSON 格式正确，不要截断"""

    @classmethod
    def extract_chapter_title(cls, content: str) -> str:
        """
        从内容中提取章节标题
        
        Args:
            content: 章节内容
            
        Returns:
            str: 章节标题
        """
        # 简单的标题提取策略：查找以数字开头的行
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('第')):
                return line
        return "未命名章节"

    @classmethod
    def calculate_similarity(cls, block1: str, block2: str) -> float:
        """
        计算两个内容块的相似度
        
        Args:
            block1: 第一个内容块
            block2: 第二个内容块
            
        Returns:
            float: 相似度分数（0-1）
        """
        doc1 = nlp(block1)
        doc2 = nlp(block2)
        return doc1.similarity(doc2)

    @classmethod
    def extract_relationships(cls, blocks: List[ContentBlock]) -> Dict[str, List[str]]:
        """
        提取内容块之间的关系
        
        Args:
            blocks: 内容块列表
            
        Returns:
            dict: 章节关系图
        """
        relationships = defaultdict(list)
        G = nx.Graph()
        
        # 创建节点
        for block in blocks:
            G.add_node(block.title)
            
        # 计算相似度并建立关系
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                score = cls.calculate_similarity(blocks[i].content, blocks[j].content)
                if score > 0.3:  # 相似度阈值
                    G.add_edge(blocks[i].title, blocks[j].title, weight=score)
                    relationships[blocks[i].title].append(blocks[j].title)
                    relationships[blocks[j].title].append(blocks[i].title)
                    
        return relationships

    @classmethod
    def split_content(cls, content: str, max_tokens: int = 2000) -> List[ContentBlock]:
        """
        将长文本内容按章节分块，并分析块间关系
        
        Args:
            content: 需要分块的内容
            max_tokens: 每块的最大token数
            
        Returns:
            list: 分块后的内容块列表
        """
        if not content:
            return []
            
        blocks = []
        current_block = ""
        current_tokens = 0
        
        # 按章节标题分隔
        lines = content.split('\n')
        current_title = ""
        
        for line in lines:
            line = line.strip()
            
            # 检测到新章节标题
            if line and (line[0].isdigit() or line.startswith('第')):
                if current_block:
                    blocks.append(ContentBlock(
                        content=current_block.strip(),
                        title=current_title
                    ))
                    current_block = ""
                current_title = line
                
            # 如果当前块加上新行会超过限制，则创建新块
            if current_tokens + len(line) > max_tokens and current_block:
                blocks.append(ContentBlock(
                    content=current_block.strip(),
                    title=current_title
                ))
                current_block = line + '\n'
                current_tokens = len(line)
                continue
                
            current_block += line + '\n'
            current_tokens += len(line)
            
        if current_block:
            blocks.append(ContentBlock(
                content=current_block.strip(),
                title=current_title
            ))
            
        # 分析块间关系
        relationships = cls.extract_relationships(blocks)
        
        # 更新每个块的相关章节信息
        for block in blocks:
            block.related_sections = relationships.get(block.title, [])
            
        return blocks

    @classmethod
    def check_coherence(cls, block1: ContentBlock, block2: ContentBlock) -> float:
        """
        检查两个相邻块的连贯性
        
        Args:
            block1: 前一个块
            block2: 后一个块
            
        Returns:
            float: 连贯性评分（0-1）
        """
        # 计算相似度
        similarity = cls.calculate_similarity(block1.content, block2.content)
        
        # 检查主题连续性
        title1 = block1.title.lower()
        title2 = block2.title.lower()
        
        # 检查是否存在重叠的关键概念
        doc1 = nlp(block1.content)
        doc2 = nlp(block2.content)
        
        overlap = len(set([token.text for token in doc1 if not token.is_stop]) & 
                     set([token.text for token in doc2 if not token.is_stop]))
        
        # 综合评分
        return (similarity + (overlap / max(len(doc1), len(doc2)))) / 2

    @classmethod
    def optimize_overlapping(cls, blocks: List[ContentBlock]) -> List[ContentBlock]:
        """
        优化重叠区域，确保内容连贯性
        
        Args:
            blocks: 内容块列表
            
        Returns:
            list: 优化后的内容块列表
        """
        optimized_blocks = []
        
        for i in range(len(blocks) - 1):
            block1 = blocks[i]
            block2 = blocks[i + 1]
            
            # 检查连贯性
            coherence = cls.check_coherence(block1, block2)
            
            if coherence < 0.5:  # 连贯性阈值
                # 添加过渡段落
                transition = f"\n\n【过渡说明】\n本节与上一节的关联：{block1.title}和{block2.title}之间存在以下关联：\n"
                for related in block1.related_sections:
                    if related == block2.title:
                        transition += f"- {related}\n"
                
                # 更新后一个块的内容
                block2.content = transition + block2.content
                
            optimized_blocks.append(block1)
            
        if blocks:
            optimized_blocks.append(blocks[-1])
            
        return optimized_blocks