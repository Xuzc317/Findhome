"""大模型接入（DeepSeek / 豆包，可切换）

用途：从**平台原文**与**房源图片**中抽取结构化信息，补规则解析的短板。

分工建议（配置 `LLM_PROVIDER`）：
- deepseek：纯文本，性价比高，适合"从标题正文里找小区名/地铁站/房型"
- doubao  ：文本 + 图片理解（火山方舟），适合"从图片里读出楼栋/地址/户型图文字"
- auto    ：有豆包用豆包（能力更全），否则退到 DeepSeek；都没有则整体不可用

设计约束：
1. 没有 Key 时 `available=False`，调用方直接跳过，不发起请求；
2. 所有输出都要求 JSON，解析失败返回 None，**绝不用模型没说的内容填空**；
3. 模型只能"读"平台给的文字和图片，不允许它凭空给出坐标或地址；
4. 调用失败只记原因，不影响主流程。
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from backend.config import get_settings, is_configured

# 位置抽取的提示词：只允许依据给定文本，不允许编造
LOCATION_PROMPT = """你是租房信息抽取助手。请**只依据下面给出的房源文本**，抽取位置信息。

严格要求：
- 找不到的字段返回 null，**绝对不要猜测或编造**
- 小区名要完整（如"麒麟花园B区"），不要只写"花园"
- 地铁站只写站名（如"深大"），不要写线路名
- 如果文本里只有商圈/行政区，把它们填到 district，community 留 null

只输出 JSON，不要任何解释：
{"community": 小区名或null, "address": 详细地址或null, "station": 地铁站名或null, "district": 行政区或null, "confidence": 0到100的整数}

房源文本：
---
{text}
---"""

# 图片抽取：要求模型描述图片里出现的地址类信息
IMAGE_PROMPT = """这是一条租房房源的图片。请找出图片中**可见的文字或可用于定位的信息**，例如：
小区门牌、楼栋号、单元号、路牌、地图截图上的地名、户型图上的"X室X厅"字样。

严格要求：
- 只报告你**确实看到**的内容，看不清就说看不清，**不要猜测**
- 没看到任何位置相关文字时，location_text 返回 null

只输出 JSON：
{"location_text": 看到的地址类文字或null, "community": 小区名或null, "layout_text": 如"3室2厅"或null, "confidence": 0到100的整数}"""


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: Optional[dict] = None


def _extract_json(text: str) -> Optional[dict]:
    """从模型回复中抠出 JSON 对象（容忍 ```json 包裹与前后废话）"""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


class LLMClient:
    """大模型客户端（OpenAI 兼容协议，DeepSeek 与火山方舟都支持）"""

    def __init__(self, provider: Optional[str] = None,
                 deepseek_key: Optional[str] = None,
                 doubao_key: Optional[str] = None,
                 timeout: Optional[float] = None):
        settings = get_settings()
        self.requested_provider = (provider or settings.llm_provider or "auto").lower()
        self.deepseek_key = (deepseek_key if deepseek_key is not None
                             else settings.deepseek_api_key or "").strip()
        self.doubao_key = (doubao_key if doubao_key is not None
                           else settings.doubao_api_key or "").strip()
        self.deepseek_model = (settings.deepseek_model or "deepseek-chat").strip()
        self.doubao_model = (settings.doubao_model or "").strip()
        self.deepseek_base = (settings.deepseek_base_url
                              or "https://api.deepseek.com").rstrip("/")
        self.doubao_base = (settings.doubao_base_url
                            or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        self.timeout = timeout or settings.llm_timeout or 60.0
        self.max_images = settings.llm_max_images or 2
        self.vision_enabled = bool(settings.llm_vision_enabled)
        self.calls = 0
        self.last_error: Optional[str] = None
        self._client = httpx.Client(timeout=self.timeout)

    # ---------- 可用性 ----------

    @property
    def provider(self) -> Optional[str]:
        """解析最终使用哪个供应商"""
        choice = self.requested_provider
        if choice == "none":
            return None
        deepseek_ok = is_configured(self.deepseek_key)
        doubao_ok = is_configured(self.doubao_key) and is_configured(self.doubao_model)
        if choice == "deepseek":
            return "deepseek" if deepseek_ok else None
        if choice == "doubao":
            return "doubao" if doubao_ok else None
        # auto
        if doubao_ok:
            return "doubao"
        if deepseek_ok:
            return "deepseek"
        return None

    @property
    def available(self) -> bool:
        return self.provider is not None

    @property
    def vision_available(self) -> bool:
        return self.available and self.provider == "doubao" and self.vision_enabled

    def describe_config(self) -> dict:
        return {
            "requested": self.requested_provider,
            "active": self.provider,
            "deepseekConfigured": is_configured(self.deepseek_key),
            "doubaoConfigured": is_configured(self.doubao_key) and is_configured(self.doubao_model),
            "doubaoModelSet": is_configured(self.doubao_model),
            "visionAvailable": self.vision_available,
        }

    # ---------- 调用 ----------

    def _endpoint(self, provider: str) -> tuple:
        if provider == "deepseek":
            return f"{self.deepseek_base}/chat/completions", self.deepseek_key, self.deepseek_model
        return f"{self.doubao_base}/chat/completions", self.doubao_key, self.doubao_model

    def chat(self, messages: List[dict], provider: Optional[str] = None,
             temperature: float = 0.0, max_tokens: int = 800) -> Optional[LLMResponse]:
        provider = provider or self.provider
        if provider is None:
            self.last_error = "未配置任何可用的大模型 Key"
            return None

        url, key, model = self._endpoint(provider)
        if not model:
            self.last_error = f"{provider} 未配置模型名/接入点 ID"
            return None

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {key}",
                   "Content-Type": "application/json"}

        self.calls += 1
        try:
            response = self._client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                self.last_error = (f"{provider} HTTP {response.status_code}: "
                                   f"{response.text[:180]}")
                return None
            data = response.json()
        except httpx.HTTPError as e:
            self.last_error = f"{provider} 网络错误: {type(e).__name__}: {e}"
            return None
        except json.JSONDecodeError:
            self.last_error = f"{provider} 返回非 JSON"
            return None

        choices = data.get("choices") or []
        if not choices:
            self.last_error = f"{provider} 返回空 choices: {str(data)[:150]}"
            return None

        content = ((choices[0].get("message") or {}).get("content")) or ""
        return LLMResponse(content=content, provider=provider, model=model,
                           usage=data.get("usage"))

    # ---------- 业务方法 ----------

    def extract_location(self, text: str, city: str = "") -> Optional[dict]:
        """从房源文本中抽取小区/地址/地铁站"""
        if not self.available or not text:
            return None
        prompt = LOCATION_PROMPT.replace("{text}", text[:3000])
        if city:
            prompt += f"\n（已知该房源在{city}，仅作参考，不要据此编造具体地点）"
        response = self.chat([{"role": "user", "content": prompt}])
        if response is None:
            return None
        data = _extract_json(response.content)
        if data is None:
            self.last_error = "模型未返回可解析的 JSON"
        return data

    def extract_layout(self, text: str) -> Optional[dict]:
        """从文本中抽取房型（规则解析置信度低时兜底）"""
        if not self.available or not text:
            return None
        prompt = (
            "从下面的租房文本中判断房型，只输出 JSON：\n"
            '{"bedrooms": 卧室数或null, "living_rooms": 厅数或null, "evidence": "依据的原文片段"}\n'
            "规则：单间/开间/主卧/次卧/床位 → bedrooms=0；找不到就返回 null，不要猜。\n"
            f"文本：\n---\n{text[:2000]}\n---"
        )
        response = self.chat([{"role": "user", "content": prompt}], max_tokens=300)
        if response is None:
            return None
        return _extract_json(response.content)

    def extract_from_image(self, image_url: str) -> Optional[dict]:
        """图片理解：读取图片中的地址/户型信息（仅豆包支持）"""
        if not self.vision_available or not image_url:
            return None

        content = [{"type": "text", "text": IMAGE_PROMPT}]
        if image_url.startswith("data:"):
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        elif image_url.startswith("http"):
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        else:
            # 本地文件 → base64
            try:
                with open(image_url, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("ascii")
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
            except OSError:
                return None

        response = self.chat([{"role": "user", "content": content}], max_tokens=500)
        if response is None:
            return None
        return _extract_json(response.content)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
