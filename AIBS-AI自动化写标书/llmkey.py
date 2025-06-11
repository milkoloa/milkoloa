import os
from openai import OpenAI
from config import Config
import logging
import json
from prompts import Prompts
import time
import asyncio
import aiohttp
from typing import List, Dict, Optional
import re
import ssl

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv('LLM_API_KEY', Config.LLM_API_KEY)
        self.base_url = os.getenv('LLM_API_BASE', Config.LLM_API_BASE)
        self.session = None
        self.messages = []
        logger.info("LLM client initialized successfully")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def _ensure_session(self):
        """确保 session 存在且有效"""
        if self.session is None or self.session.closed:
            # 配置 SSL 上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            
            # 配置连接超时
            timeout = aiohttp.ClientTimeout(
                total=Config.TIMEOUT,  # Overall timeout for the entire operation (resolve, connect, send, headers, body)
                connect=10,          # Max time to establish a connection
                sock_read=20         # Max time to read a portion of the response body
            )
            
            # 确保 base_url 以斜杠结尾
            base_url = self.base_url
            if not base_url.endswith('/'):
                base_url += '/'
            
            # 配置连接器
            connector_kwargs = {
                'ssl': ssl_context,
                'limit': 15,  # 调整并发连接数
                'force_close': True,
                'enable_cleanup_closed': True
            }
            
            connector = aiohttp.TCPConnector(**connector_kwargs)
            
            # 创建会话
            session_kwargs = {
                'base_url': base_url,
                'headers': {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                'timeout': timeout,
                'connector': connector
            }
            
            # 如果使用代理，添加代理配置到会话
            if Config.USE_PROXY:
                session_kwargs['proxy'] = Config.PROXY_URLS['https']
                logger.info(f"Using proxy: {Config.PROXY_URLS}")
            
            self.session = aiohttp.ClientSession(**session_kwargs)
            
            logger.info(f"Created new session with base URL: {base_url}")

    async def _call_llm_async(self, messages: list, require_json: bool = False, require_outline: bool = False) -> Optional[str]:
        """
        异步调用 LLM API。
        包含重试逻辑，当请求超时、遇到速率限制 (429) 或其他可重试的服务器错误时，
        会使用指数退避策略进行重试 (Retry with exponential backoff).
        """
        await self._ensure_session()
        retry_count = 0
        
        # Retry loop with exponential backoff
        while retry_count <= Config.MAX_RETRIES:
            try:
                request_params = {
                    "model": Config.LLM_MODEL,
                    "messages": messages,
                    "temperature": Config.TEMPERATURE,
                    "max_tokens": Config.MAX_TOKENS,
                    "top_p": Config.TOP_P
                }

                logger.info(f"Sending request to LLM. Model: {Config.LLM_MODEL}, Messages count: {len(messages)}")
                logger.debug(f"Sending request with params: {json.dumps(request_params, ensure_ascii=False)}")

                async with self.session.post(
                    "chat/completions",
                    json=request_params,
                    timeout=Config.TIMEOUT
                ) as response:
                    # 首先记录原始响应
                    response_text = await response.text()
                    logger.debug(f"Raw API response: {response_text}")
                    
                    # Check response status
                    if response.status == 429:
                        logger.warning(f"Rate limit hit (429). Raw response: {response_text}")
                        retry_after = response.headers.get("Retry-After")
                        wait_time = Config.RETRY_DELAY * (Config.RETRY_BACKOFF ** retry_count) # Default backoff
                        if retry_after:
                            try:
                                wait_time = int(retry_after)
                                logger.info(f"Using Retry-After header: waiting for {wait_time} seconds.")
                            except ValueError:
                                logger.warning(f"Could not parse Retry-After header: '{retry_after}'. Falling back to exponential backoff.")
                        
                        retry_count += 1
                        if retry_count <= Config.MAX_RETRIES:
                            logger.warning(f"Rate limit: Retrying in {wait_time} seconds... (Attempt {retry_count}/{Config.MAX_RETRIES})")
                            await asyncio.sleep(wait_time)
                            continue 
                        else:
                            logger.error("Request failed after maximum retries due to rate limiting.")
                            return None
                    elif response.status != 200:
                        logger.error(f"API returned status {response.status}: {response_text}")
                        # This is a non-429, non-200 error. Decide if retry is appropriate.
                        # The ClientResponseError handler below might also catch this if aiohttp raises it.
                        # For now, let's treat it as a server error and use the generic retry mechanism.
                        # This could be made more specific (e.g. only retry on 5xx errors)
                        # The aiohttp.ClientResponseError exception below will handle cases where aiohttp itself raises an error.
                        # If aiohttp does not raise an exception for this status, this code handles the retry.
                        
                        # Fall through to general retry logic in exception handlers if this status also causes an exception,
                        # or handle retry here if it doesn't.
                        # To avoid potential double retries if an exception IS raised by aiohttp for this status,
                        # we can just log here and let the exception handlers manage retries for actual exceptions.
                        # However, if aiohttp doesn't raise an exception for e.g. a 500 that returns a body,
                        # we would need a retry here.
                        # Let's assume for now that critical errors that should be retried will be raised as exceptions by aiohttp
                        # or are handled by specific status checks like 429.
                        # So, if it's not 200 and not 429, and aiohttp hasn't raised an exception, it's an unexpected success-like failure.
                        # For robustness, we might still want to retry a few times.
                        retry_count += 1
                        if retry_count <= Config.MAX_RETRIES:
                            wait_time = Config.RETRY_DELAY * (Config.RETRY_BACKOFF ** (retry_count - 1))
                            logger.warning(f"API error {response.status}. Retrying in {wait_time} seconds... (Attempt {retry_count}/{Config.MAX_RETRIES})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Request failed after maximum retries due to API error {response.status}.")
                            return None

                    # Successful response (200 OK)
                    result = json.loads(response_text)
                    
                    # 提取内容
                    if "choices" in result and result["choices"] and "message" in result["choices"][0]:
                        content = result["choices"][0]["message"]["content"].strip()
                        
                        # 如果需要 JSON 格式，尝试解析
                        if require_json:
                            try:
                                if content.startswith('```'):
                                    content = re.sub(r'^```(?:json)?\s*|\s*```\s*$', '', content)
                                json_obj = json.loads(content)
                                content = json.dumps(json_obj, ensure_ascii=False, indent=2)
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON in response: {e}. Content: {content}") # Already logs content
                                raise
                        
                        logger.info(f"Received response from LLM. Content length: {len(content)} chars")
                        return content
                    else:
                        logger.error(f"Unexpected response structure: {result}")
                        raise ValueError("Invalid response structure")

            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count <= Config.MAX_RETRIES:
                    wait_time = Config.RETRY_DELAY * (Config.RETRY_BACKOFF ** (retry_count - 1)) # Consistent variable name
                    logger.warning(f"Request timeout. Retrying in {wait_time} seconds... (Attempt {retry_count}/{Config.MAX_RETRIES})")
                    await asyncio.sleep(wait_time)
                    # No continue here, the loop structure will handle it.
                else:
                    logger.error("Request failed after maximum retries due to timeout.")
                    return None
            except aiohttp.ClientResponseError as e: # Catching specific aiohttp client errors
                logger.error(f"AIOHTTP ClientResponseError: {e.status} - {e.message}. Response headers: {e.headers}")
                # Handle 429 specifically if it's raised as ClientResponseError
                if e.status == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait_time = Config.RETRY_DELAY * (Config.RETRY_BACKOFF ** retry_count) # Default backoff
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                            logger.info(f"Using Retry-After header from ClientResponseError: waiting for {wait_time} seconds.")
                        except ValueError:
                            logger.warning(f"Could not parse Retry-After header from ClientResponseError: '{retry_after}'. Falling back to exponential backoff.")
                    
                    retry_count += 1
                    if retry_count <= Config.MAX_RETRIES:
                        logger.warning(f"Retrying in {wait_time} seconds... (Attempt {retry_count}/{Config.MAX_RETRIES})")
                        await asyncio.sleep(wait_time)
                        continue # Continue to next retry iteration
                    else:
                        logger.error("Request failed after maximum retries due to rate limiting (ClientResponseError).")
                        return None
                else: # For other ClientResponseErrors, decide if retry is appropriate
                    retry_count += 1
                    if retry_count <= Config.MAX_RETRIES:
                        wait_time = Config.RETRY_DELAY * (Config.RETRY_BACKOFF ** (retry_count - 1))
                        logger.warning(f"ClientResponseError {e.status}. Retrying in {wait_time} seconds... (Attempt {retry_count}/{Config.MAX_RETRIES})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Request failed after maximum retries due to ClientResponseError {e.status}.")
                        return None
            except Exception as e: # General exception catch, should be more specific if possible
                logger.error(f"An unexpected error occurred: {e}", exc_info=True)
                # This general exception might not be suitable for retry, depends on the error.
                # For now, let's not retry on general exceptions to avoid retry loops on non-transient issues.
                # Consider if specific exceptions should be caught and retried.
                # raise # Or return None, depending on desired behavior for unexpected errors
                return None # For now, return None on unhandled exceptions within the retry loop

    async def generate_section_content_async(self, section: Dict) -> Dict:
        """异步生成单个章节内容"""
        try:
            # 开始生成
            logger.info(f"=== Generating content for section: {section['title']} ===")
            #logger.info(f"Content boundary: {section['content_summary'][:100]}...")  # 只显示前100个字符
            start_time = time.time()

            prompt = Prompts.CONTENT_SECTION_USER.format(
                tech_req_md=section['tech_req_md'],
                scoring_criteria_md=section['scoring_criteria_md'],
                full_outline_md=section['full_outline_md'],
                title=section['title'],
                content_summary=section['content_summary']
            )
            
            content = await self._call_llm_async([
                {"role": "system", "content": Prompts.CONTENT_SYSTEM_ROLE},
                {"role": "user", "content": prompt}
            ])

            # 完成生成
            elapsed_time = time.time() - start_time
            if content:
                content_length = len(content)
                logger.info(f"✓ Successfully generated {content_length} chars for {section['title']} in {elapsed_time:.2f}s")
            else:
                logger.error(f"✗ Failed to generate content for {section['title']} after {elapsed_time:.2f}s")

            return {
                'title': section['title'],
                'content': content if content else "生成失败，请手动补充。"
            }
        except Exception as e:
            logger.error(f"✗ Error generating content for {section['title']}: {str(e)}")
            return {
                'title': section['title'],
                'content': f"生成失败：{str(e)}"
            }

    async def generate_content_init_async(self, tech_content: str, score_content: str, outline: str) -> bool:
        """初始化内容生成的背景信息"""
        try:
            prompt = Prompts.CONTENT_INIT_USER.format(
                tech_content=tech_content,
                score_content=score_content,
                outline=outline
            )
            self.start_new_chat(Prompts.CONTENT_SYSTEM_ROLE)
            response = await self.generate_chat_text_async(prompt)
            return bool(response)
        except Exception as e:
            logger.error(f"Error initializing content generation: {e}")
            return False

    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def start_new_chat(self, system_role: str):
        """开始新的对话"""
        self.messages = [{"role": "system", "content": system_role}]
        
    def add_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.messages.append({"role": role, "content": content})
        
    async def generate_text_async(self, prompt=None, system_role=None, messages=None, require_json=False, require_outline=False) -> str:
        """异步生成文本
        :param prompt: 单条提示词
        :param system_role: 系统角色设定
        :param messages: 完整的消息列表（如果提供，则忽略 prompt 和 system_role）
        :param require_json: 是否要求 JSON 格式响应
        :param require_outline: 是否要求大纲格式（包含 body_paragraphs 字段）
        """
        try:
            if messages is None:
                messages = [
                    {"role": "system", "content": system_role or Prompts.OUTLINE_SYSTEM_ROLE},
                    {"role": "user", "content": prompt}
                ]
            
            return await self._call_llm_async(messages, require_json=require_json, require_outline=require_outline)
        except Exception as e:
            logger.error(f"Error in generate_text: {e}", exc_info=True)
            return None
            
    async def generate_chat_text_async(self, prompt: str) -> str:
        """异步在现有对话中生成文本（用于内容生成）"""
        try:
            self.add_message("user", prompt)
            response = await self._call_llm_async(self.messages, require_json=False)
            if response:
                self.add_message("assistant", response)
            return response
        except Exception as e:
            logger.error(f"Error in generate_chat_text: {e}", exc_info=True)
            return None