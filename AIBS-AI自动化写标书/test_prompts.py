from prompts import Prompts
import json

def test_prompts():
    try:
        # 测试数据
        tech_content = """
        1. 系统架构要求
        - 需采用微服务架构
        - 支持分布式部署
        - 需要高可用设计
        """
        
        score_content = """
        1. 技术方案评分（40分）
        - 系统架构设计（15分）
        - 技术路线选择（10分）
        - 实施方案（15分）
        """
        
        # 测试大纲生成
        print("\n测试大纲生成提示词:")
        outline_prompts = Prompts.generate_outline_prompt(tech_content, score_content)
        for key, value in outline_prompts.items():
            print(f"\n{key}:")
            print(value)
            
        # 测试大纲验证
        print("\n测试大纲验证:")
        test_outline = """{
            "body_paragraphs": [
                {
                    "chapter_title": "第一章 系统架构设计",
                    "sections": [
                        {
                            "section_title": "1.1 系统架构",
                            "sub_sections": [
                                {
                                    "sub_section_title": "1.1.1 微服务架构设计",
                                    "content_summary": "微服务架构设计说明"
                                }
                            ]
                        }
                    ]
                }
            ]
        }"""
        
        try:
            Prompts.validate_outline(test_outline)
            print("大纲格式验证通过")
        except ValueError as e:
            print(f"大纲格式验证失败: {str(e)}")
            
        # 测试内容分块
        print("\n测试内容分块:")
        test_content = """
        第一章 系统架构设计
        1.1 系统架构
        1.1.1 微服务架构设计
        1.1.2 部署架构设计
        
        第二章 技术实现
        2.1 核心技术
        2.1.1 微服务实现
        2.1.2 部署实现
        """
        
        blocks = Prompts.split_content(test_content)
        print(f"\n分块数量: {len(blocks)}")
        for i, block in enumerate(blocks):
            print(f"\n块 {i+1}:")
            print(f"标题: {block.title}")
            print(f"内容: {block.content}")
            print(f"相关章节: {block.related_sections}")
            
        # 测试连贯性检查
        print("\n测试连贯性检查:")
        optimized_blocks = Prompts.optimize_overlapping(blocks)
        print(f"\n优化后的块数量: {len(optimized_blocks)}")
        for i, block in enumerate(optimized_blocks):
            print(f"\n优化后的块 {i+1}:")
            print(f"标题: {block.title}")
            print(f"内容: {block.content}")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

if __name__ == "__main__":
    test_prompts()
