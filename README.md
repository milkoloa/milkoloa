- 📫 How to reach me ...15138765345
# AIBS 标书生成器（AI Bid Document Generator）

## 项目简介
AIBS 标书生成器是一个基于 AI 的自动化标书生成工具。你只需提供技术要求和评分标准，系统会自动帮你生成结构化的标书大纲和详细内容，大大提升标书编写效率。

---

## 功能亮点
- **智能分析**：自动理解技术需求和评分标准。
- **大纲生成**：一键生成标准的三级文档大纲。
- **内容生成**：根据大纲自动填充详细内容。
- **分块优化**：内容分块、连贯性自动优化。
- **高效并发**：支持异步API调用，速度快。
- **配置灵活**：支持多种大模型API和自定义参数。

---

## 环境依赖
- Python 3.8 及以上
- pip（Python 包管理器）
- 推荐：spaCy 中文大模型（提升内容分块与相似度分析效果）

### 依赖包一览
项目依赖已写在 `requirements.txt`，主要包括：
- Flask / Quart / aiohttp（Web服务与异步支持）
- spacy（自然语言处理）
- nltk、networkx、python-Levenshtein（文本分析与相似度）

---

## 安装与配置（一步步教你）

1. **克隆项目**
   ```bash
   git clone <你的仓库地址>
   cd <项目目录>
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **安装 spaCy 中文大模型（强烈推荐）**
   ```bash
   python -m spacy download zh_core_web_trf
   ```
   > 没装大模型也能用，但内容相似度分析会不准确，且有警告。

4. **配置环境变量**
   - 新建 `.env` 文件，或直接在系统环境变量中设置：
     - `LLM_API_KEY`：你的大模型API密钥（必填）
     - `LLM_API_BASE`：API地址（可选）
     - `LLM_MODEL`：模型名称（可选）
   - 也可以直接修改 `config.py` 里的默认值。

5. **准备输入文件**
   - 在 `inputs/` 目录下放入：
     - `tech.md`：技术要求
     - `score.md`：评分标准

6. **运行主程序**
   ```bash
   python app.py
   ```
   - 启动后可通过浏览器访问 Web 页面，或用 Postman 调用 API。

7. **运行测试（可选）**
   ```bash
   python test_prompts.py
   ```

---

## 常见问题（FAQ）

**Q1：运行时出现 spaCy 警告 `[W007] The model you're using has no word vectors loaded...` 怎么办？**
A1：请安装 spaCy 中文大模型：
```bash
python -m spacy download zh_core_web_trf
```

**Q2：依赖安装失败怎么办？**
A2：请升级 pip 并确保 Python 版本符合要求。
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Q3：API KEY 怎么获取？**
A3：请根据你选用的大模型服务（如 OpenAI、智谱、通义等）注册并获取 API KEY。

**Q4：如何自定义提示词？**
A4：可在 Web 页面"提示词配置"中自定义，也可直接修改 `prompts.py`。

---

## 项目结构说明
```
├── app.py                # 主程序（Web服务与API）
├── bidding_workflow.py   # 标书生成核心流程
├── llmkey.py             # 大模型API调用封装
├── config.py             # 配置文件
├── prompts.py            # 提示词模板与分块逻辑
├── requirements.txt      # 依赖包列表
├── inputs/               # 输入文件目录（技术要求、评分标准）
├── outputs/              # 输出文件目录（大纲、内容）
├── templates/            # 前端页面模板
├── logs/                 # 日志文件
└── test_prompts.py       # 测试脚本
```

---

## 联系与支持/15138765345
如有问题、建议或合作意向，欢迎在 GitHub 提 Issue 或 PR。

---

**祝你用 AI 写标书更高效！**

---

# 后端API接口文档

## 1. 上传招标书

### `POST /api/upload_bid`

**功能**：上传招标书文件，自动解析并返回结构化内容。

**请求参数**（form-data）：
| 字段名 | 类型   | 必填 | 说明                |
|--------|--------|------|---------------------|
| file   | file   | 是   | 招标书文件（PDF/Word/Markdown/纯文本） |

**返回示例**（JSON）：
```json
{
  "success": true,
  "tech_content": "技术要求内容...",
  "score_content": "评分标准内容...",
  "raw_text": "完整文本内容...",
  "message": "解析成功"
}
```

---

## 2. 上传历史标书

### `POST /api/upload_history`

**功能**：上传历史标书文件，供AI参考。

**请求参数**（form-data）：
| 字段名 | 类型   | 必填 | 说明                |
|--------|--------|------|---------------------|
| files  | file[] | 是   | 多个历史标书文件    |

**返回示例**（JSON）：
```json
{
  "success": true,
  "history_ids": ["xxx.docx", "yyy.pdf"],
  "message": "上传成功"
}
```

---

## 3. 生成大纲

### `POST /api/generate_outline`

**功能**：根据技术要求、评分标准（和可选历史标书）生成标书大纲。

**请求参数**（JSON）：
| 字段名        | 类型     | 必填 | 说明                |
|---------------|----------|------|---------------------|
| tech_content  | string   | 是   | 技术要求内容        |
| score_content | string   | 是   | 评分标准内容        |
| history_ids   | string[] | 否   | 历史标书ID列表      |
| model         | string   | 否   | 指定大模型类型      |
| api_key       | string   | 否   | 指定API KEY         |

**返回示例**（JSON）：
```json
{
  "success": true,
  "outline": { "system_role": "...", "tech_prompt": "...", ... },
  "message": "生成成功"
}
```

---

## 4. 生成内容

### `POST /api/generate_content`

**功能**：根据大纲、技术要求、评分标准等生成标书正文内容。

**请求参数**（JSON）：
| 字段名        | 类型     | 必填 | 说明                |
|---------------|----------|------|---------------------|
| outline       | object   | 是   | 标书大纲结构        |
| tech_content  | string   | 是   | 技术要求内容        |
| score_content | string   | 是   | 评分标准内容        |
| template_id   | int      | 否   | 模板ID              |
| model         | string   | 否   | 指定大模型类型      |
| api_key       | string   | 否   | 指定API KEY         |

**返回示例**（JSON）：
```json
{
  "success": true,
  "content_blocks": [
    {"title": "1.1 xxx", "content": "内容...", "related_sections": [...]},
    ...
  ],
  "message": "生成成功"
}
```

---

## 5. 导出文档

### `POST /api/export`

**功能**：将生成的内容导出为 Markdown、PDF、Word 等格式。

**请求参数**（JSON）：
| 字段名        | 类型     | 必填 | 说明                |
|---------------|----------|------|---------------------|
| content_blocks| object[] | 是   | 内容分块数组        |
| format        | string   | 是   | 导出格式（markdown/pdf/word） |

**返回**：文件流（Content-Disposition: attachment; filename=bid.xxx）

---

## 6. 模板管理

### `GET /api/prompts/variables`
**功能**：获取所有提示词模板。

**返回示例**（JSON）：
```json
{
  "OUTLINE_SYSTEM_ROLE": "...",
  "OUTLINE_TECH_USER": "...",
  "OUTLINE_SCORE_USER": "...",
  "OUTLINE_GENERATE_USER": "...",
  "CONTENT_SYSTEM_ROLE": "...",
  "CONTENT_INIT_USER": "...",
  "CONTENT_SECTION_USER": "..."
}
```

### `POST /api/prompts/variables`
**功能**：保存自定义提示词模板。

**请求参数**（JSON）：同上

**返回示例**（JSON）：
```json
{
  "success": true
}
```

---

## 7. 获取/设置模型配置

### `GET /api/model_config`
**功能**：获取当前大模型类型和API KEY。

**返回示例**（JSON）：
```json
{
  "success": true,
  "model": "openai",
  "api_key": "sk-xxx"
}
```

### `POST /api/model_config`
**功能**：设置大模型类型和API KEY。

**请求参数**（JSON）：
| 字段名 | 类型   | 必填 | 说明                |
|--------|--------|------|---------------------|
| model  | string | 是   | 大模型类型          |
| api_key| string | 是   | API KEY             |

**返回示例**（JSON）：
```json
{
  "success": true,
  "model": "openai",
  "api_key": "sk-xxx"
}
```

---

**统一说明**：
- 所有接口返回均建议包含 `success` 字段和 `message` 字段，便于前端判断和提示。
- 文件上传接口建议限制大小和类型，防止恶意上传。
- 导出接口返回为文件流，前端需处理下载。
- 所有接口建议加异常处理，返回 `success: false` 和详细错误信息。

