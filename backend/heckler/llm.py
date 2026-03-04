"""
LLM integration module with multi-backend support.

Supports three backends configured via config.yaml llm_backend field:
- "claude"        : Anthropic Claude API (ANTHROPIC_API_KEY env var required)
- "ollama_remote" : Ollama on a remote machine (e.g. gaming laptop)
- "ollama_local"  : Ollama on this machine with a small CPU-friendly model

This module handles:
- Communication with the chosen LLM backend
- Context window management (sliding window + salience markers)
- Public vs private LLM requests
- Memory compression and summarization
"""

import json
import logging
import os
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypedDict

import httpx

logger = logging.getLogger(__name__)


class MemeResponse(TypedDict):
    """Structured meme response from LLM."""

    response_type: Literal["meme"]
    template: str
    args: list[str]
    caption: str | None


class TextResponse(TypedDict):
    """Structured text response from LLM."""

    response_type: Literal["text"]
    content: str


Response = MemeResponse | TextResponse


@dataclass
class CodeBlock:
    """Represents an evaluated SuperCollider code block with metadata."""

    code: str
    timestamp: datetime
    salience: int = 0  # Higher = more important, persists longer
    summary: str | None = None  # Compressed version for older blocks

    def is_salient(self) -> bool:
        """Check if this block should be marked as important."""
        salient_keywords = ["Ndef", "Pdef", "Tdef", "SynthDef", "play", "clear", "stop"]
        return any(keyword in self.code for keyword in salient_keywords)


@dataclass
class ConversationMemory:
    """Manages LLM context with temporal awareness."""

    max_recent_blocks: int = 5
    max_total_blocks: int = 20

    blocks: deque[CodeBlock] = field(default_factory=deque)
    summaries: list[str] = field(default_factory=list)

    def add_block(self, code: str) -> CodeBlock:
        """Add a new code block to memory."""
        block = CodeBlock(
            code=code,
            timestamp=datetime.now(),
            salience=1 if self._is_salient(code) else 0,
        )

        self.blocks.append(block)

        if len(self.blocks) > self.max_total_blocks:
            self.blocks.popleft()

        return block

    def _is_salient(self, code: str) -> bool:
        """Determine if code block is musically important."""
        salient_keywords = ["Ndef", "Pdef", "Tdef", "SynthDef", "play", "clear", "stop"]
        has_large_numbers = any(
            token.replace(".", "").isdigit() and float(token) > 100
            for token in code.split()
            if token.replace(".", "").replace("-", "").isdigit()
        )
        return any(keyword in code for keyword in salient_keywords) or has_large_numbers

    def get_context_prompt(self) -> str:
        """Build context prompt with weighted recency."""
        if not self.blocks:
            return "No previous code has been evaluated yet."

        context_parts = []

        if self.summaries:
            context_parts.append("## Performance History Summary")
            context_parts.extend(self.summaries)
            context_parts.append("")

        recent_blocks = list(self.blocks)[-self.max_recent_blocks :]
        if recent_blocks:
            context_parts.append("## Recent Evaluations")
            for i, block in enumerate(recent_blocks, 1):
                age = (datetime.now() - block.timestamp).total_seconds()
                context_parts.append(
                    f"{i}. [{int(age)}s ago{' - IMPORTANT' if block.salience else ''}]\n{block.code}"
                )
            context_parts.append("")

        return "\n".join(context_parts)

    async def compress_history(self, client: "OllamaClient") -> str:
        """Create a private summary of older blocks (not displayed to audience)."""
        if len(self.blocks) < self.max_recent_blocks:
            return ""

        old_blocks = list(self.blocks)[: -self.max_recent_blocks]
        if not old_blocks:
            return ""

        codes = "\n\n".join(f"Block {i}: {b.code}" for i, b in enumerate(old_blocks, 1))

        summary = await client.request_private_summary(codes)
        self.summaries.append(summary)

        for _ in range(len(old_blocks)):
            if len(self.blocks) > self.max_recent_blocks:
                self.blocks.popleft()

        return summary


class OllamaClient:
    """
    LLM client supporting multiple backends: Claude API, remote Ollama, local Ollama.

    Backend is selected at construction time via the `backend` parameter.
    """

    def __init__(
        self,
        backend: Literal["claude", "ollama_remote", "ollama_local"] = "ollama_remote",
        # Ollama options (used for ollama_remote and ollama_local)
        host: str = "localhost",
        port: int = 11434,
        model: str = "mistral:7b",
        # Claude options
        claude_model: str = "claude-haiku-4-5-20251001",
        # Shared options
        temperature: float = 0.8,
        timeout: float = 30.0,
        meme_min_interval: int = 5,
        meme_max_interval: int = 10,
    ):
        self.backend = backend
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.claude_model = claude_model
        self.temperature = temperature
        self.timeout = timeout
        self.memory = ConversationMemory()
        self.available = False  # Track backend availability

        # Meme generation state
        self.meme_min_interval = meme_min_interval
        self.meme_max_interval = meme_max_interval
        self.text_responses_since_meme = 0
        self.meme_threshold = self._generate_meme_threshold()

        # Lazy-init Anthropic client (only if needed)
        self._anthropic = None

        self.meme_templates = {
            # 1 arg
            "ItsRetarded": 1,
            "Headache": 1,
            "ClassNote": 1,
            "NutButton": 1,
            "Pills": 1,
            "Loud": 1,
            "Milk": 1,
            "Finally": 1,
            "Hate": 1,
            "Trump": 1,
            # 2 args
            "MeAlsoMe": 2,
            "ItsTime": 2,
            "Classy": 2,
            "Cola": 2,
            "Cliff": 2,
            "Knight": 2,
            "Vape": 2,
            "ButGodSaid": 2,
            # 3 args
            "Balloon": 3,
            "PredatorHandshake": 3,
            "BellCurve": 3,
        }

    def _get_anthropic_client(self):
        """Lazily create the Anthropic async client."""
        if self._anthropic is None:
            import anthropic
            self._anthropic = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
        return self._anthropic

    def _generate_meme_threshold(self) -> int:
        return self.meme_min_interval + random.randint(
            0, self.meme_max_interval - self.meme_min_interval
        )

    def _validate_meme_args(self, response: MemeResponse) -> tuple[bool, str]:
        template = response.get("template")
        args = response.get("args", [])

        if template not in self.meme_templates:
            return False, f"Unknown template '{template}'"

        expected_count = self.meme_templates[template]
        actual_count = len(args)

        if actual_count != expected_count:
            return False, (
                f"Template '{template}' requires {expected_count} args, "
                f"but you provided {actual_count} args. "
                f"Please generate exactly {expected_count} text arguments."
            )

        return True, ""

    # ------------------------------------------------------------------
    # Backend dispatch: structured commentary
    # ------------------------------------------------------------------

    async def _call_structured(self, prompt: str, schema: dict) -> Response:
        """Call the active backend and return a parsed structured Response."""
        if self.backend == "claude":
            return await self._call_claude_structured(prompt, schema)
        else:
            return await self._call_ollama_structured(prompt, schema)

    async def _call_ollama_structured(self, prompt: str, schema: dict) -> Response:
        """Call Ollama with JSON schema format."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": schema,
                    "options": {
                        "temperature": self.temperature,
                        "num_ctx": 4096,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return json.loads(result["response"])

    async def _call_claude_structured(self, prompt: str, schema: dict) -> Response:
        """Call Claude API using tool use for structured output.

        Claude's tool input_schema does not support oneOf/allOf/anyOf at the top
        level, so we use a flat schema with all fields optional and rely on
        response_type to discriminate.
        """
        import anthropic

        client = self._get_anthropic_client()

        # Flat schema compatible with Claude tool use restrictions
        flat_schema = {
            "type": "object",
            "properties": {
                "response_type": {
                    "type": "string",
                    "enum": ["text", "meme"],
                    "description": "Whether this is a text comment or a meme",
                },
                "content": {
                    "type": "string",
                    "description": "Text commentary (required when response_type is 'text')",
                },
                "template": {
                    "type": "string",
                    "enum": list(self.meme_templates.keys()),
                    "description": "Meme template name (required when response_type is 'meme')",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Text arguments for the meme template (required when response_type is 'meme')",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption below the meme",
                },
            },
            "required": ["response_type"],
        }

        tools = [
            {
                "name": "respond",
                "description": "Output your heckler response",
                "input_schema": flat_schema,
            }
        ]

        message = await client.messages.create(
            model=self.claude_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice={"type": "any"},
        )

        # Extract tool call result
        for block in message.content:
            if block.type == "tool_use" and block.name == "respond":
                return block.input

        raise ValueError(f"Claude did not return a tool use block: {message.content}")

    # ------------------------------------------------------------------
    # Backend dispatch: plain text (for private summaries)
    # ------------------------------------------------------------------

    async def _call_plain(self, prompt: str, temperature: float = 0.5) -> str:
        """Call the active backend for a plain text response."""
        if self.backend == "claude":
            return await self._call_claude_plain(prompt)
        else:
            return await self._call_ollama_plain(prompt, temperature)

    async def _call_ollama_plain(self, prompt: str, temperature: float = 0.5) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 4096,
                    },
                },
            )
            response.raise_for_status()
            return response.json()["response"]

    async def _call_claude_plain(self, prompt: str) -> str:
        client = self._get_anthropic_client()
        message = await client.messages.create(
            model=self.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_commentary(self, code: str) -> Response:
        """Generate public LLM commentary for evaluated code (displayed to audience)."""
        self.memory.add_block(code)
        context = self.memory.get_context_prompt()

        if not self.available:
            logger.debug("Using mock LLM response (backend unavailable)")
            return TextResponse(
                response_type="text",
                content=f"[Mock LLM] Received code: {code[:50]}...",
            )

        should_request_meme = self.text_responses_since_meme >= self.meme_threshold
        logger.info(
            f"Response decision: text_count={self.text_responses_since_meme}, "
            f"threshold={self.meme_threshold}, requesting_meme={should_request_meme}"
        )

        prompt = self._build_commentary_prompt(context, code, request_meme=should_request_meme)

        schema = {
            "type": "object",
            "required": ["response_type"],
            "oneOf": [
                {
                    "properties": {
                        "response_type": {"const": "text"},
                        "content": {
                            "type": "string",
                            "description": "Your commentary text (1-2 sentences)",
                        },
                    },
                    "required": ["response_type", "content"],
                    "additionalProperties": False,
                },
                {
                    "properties": {
                        "response_type": {"const": "meme"},
                        "template": {
                            "type": "string",
                            "enum": list(self.meme_templates.keys()),
                            "description": "Meme template name",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Text for each meme panel",
                        },
                        "caption": {
                            "type": "string",
                            "description": "Optional caption below meme",
                        },
                    },
                    "required": ["response_type", "template", "args"],
                    "additionalProperties": False,
                },
            ],
        }

        try:
            parsed: Response = await self._call_structured(prompt, schema)

            # Validate meme responses and retry once if invalid
            if parsed["response_type"] == "meme":
                is_valid, error_msg = self._validate_meme_args(parsed)
                if not is_valid:
                    logger.warning(f"Invalid meme response: {error_msg}")
                    logger.info("Retrying with error feedback...")

                    retry_prompt = f"""{prompt}

ERROR FROM PREVIOUS ATTEMPT:
{error_msg}

Please try again, ensuring you provide the correct number of arguments."""

                    try:
                        parsed = await self._call_structured(retry_prompt, schema)

                        if parsed["response_type"] == "meme":
                            is_valid_retry, error_msg_retry = self._validate_meme_args(parsed)
                            if not is_valid_retry:
                                logger.error(f"Retry also failed: {error_msg_retry}")
                                return TextResponse(
                                    response_type="text",
                                    content="[Meme generation failed - arg count mismatch]",
                                )
                        logger.info("Retry successful!")

                    except Exception as retry_err:
                        logger.error(f"Retry failed: {retry_err}")
                        return TextResponse(response_type="text", content="[Meme retry failed]")

            if parsed["response_type"] == "meme":
                self.text_responses_since_meme = 0
                self.meme_threshold = self._generate_meme_threshold()
                logger.info(f"Meme generated. Reset counter. New threshold: {self.meme_threshold}")
            else:
                self.text_responses_since_meme += 1
                logger.debug(
                    f"Text response. Counter: {self.text_responses_since_meme}/{self.meme_threshold}"
                )

            logger.info(f"LLM response: {parsed}")
            return parsed

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            self.text_responses_since_meme += 1
            return TextResponse(response_type="text", content=f"[LLM Error: {e}]")

    async def request_private_summary(self, old_codes: str) -> str:
        """Request a private summary (not displayed to audience)."""
        prompt = f"""You are summarizing a live coding performance for internal memory management.
Compress these older SuperCollider code evaluations into a brief musical trajectory summary.
Focus on: key patterns established, synthesis techniques used, structural changes.

OLD CODE BLOCKS:
{old_codes}

Provide a 2-3 sentence summary of the musical direction so far:"""

        try:
            return await self._call_plain(prompt, temperature=0.5)
        except Exception as e:
            logger.error(f"Private summary failed: {e}")
            return "[Summary unavailable]"

    def _build_commentary_prompt(
        self, context: str, new_code: str, request_meme: bool = False
    ) -> str:
        """Build the prompt for public commentary."""
        from . import memes

        template_info = memes.get_meme_metadata_for_llm()

        if request_meme:
            return f"""
You are a snarky heckler at a live coding performance. Generate a MEME to react to the SuperCollider code that was just evaluated.

PERFORMANCE CONTEXT:
{context}

NEW CODE EVALUATED:
{new_code}

YOUR TASK:
1. First, identify which template best fits this moment
2. Check how many args that template requires (1, 2, or 3)
3. Generate EXACTLY that many text arguments - no more, no less
4. Write punchy, sarcastic text that roasts or comments on the code/performance

MEME STYLE:
- Be sarcastic and irreverent but not mean
- Reference the actual code patterns (Ndef, SynthDef, parameter values, etc.)
- Call out repetitive patterns, weird choices, or impressive moments
- Keep each text argument under the character limit

AVAILABLE MEME TEMPLATES:
{template_info}

EXAMPLE RESPONSES:

1-arg template example:
{{
  "response_type": "meme",
  "template": "Pills",
  "args": ["just use SinOsc like a normal person"]
}}

2-arg template example:
{{
  "response_type": "meme",
  "template": "MeAlsoMe",
  "args": ["learning actual synthesis techniques", "just polling LFNoise0 forever"]
}}

3-arg template example:
{{
  "response_type": "meme",
  "template": "Balloon",
  "args": ["me", "writing interesting musical code", "{{ LFNoise0.ar(8) }}.poll;"]
}}

CRITICAL RULES:
- ONLY return the meme response format (response_type, template, args)
- Your args array MUST have EXACTLY the right number of elements for your chosen template
- 1-arg templates need ["text"], 2-arg templates need ["text1", "text2"], 3-arg templates need ["text1", "text2", "text3"]
- Keep each arg under the character limit shown
- Do NOT include content field"""

        return f"""
You are a snarky heckler at a live coding performance. Your job is to provide brief, witty commentary on the SuperCollider code being evaluated.

STYLE:
- Default to brief responses (one word, short phrase, or single sentence)
- Only get verbose when something genuinely significant happens (new synths, changes, weird choices)
- Be sarcastic and irreverent, but not mean
- Focus on the musical result, not just the code
- Vary your reactions - don't repeat yourself
- Drop references to pop or classical music when relevant
- Feel free to use emojis sparingly for emphasis

WHEN TO BE BRIEF (most of the time):
- Small parameter tweaks → single word: "Sure.", "Yikes.", "Hm.", "Again?", "Bold."
- Repetitive patterns → dismissive: "Still at it?", "Cool.", "Riveting."
- Minor edits → skeptical: "Really?", "Why though?", "..."

WHEN TO SAY MORE (rarely):
- Brand new Ndef/Pdef/SynthDef → 1-2 sentence roast or explanation
- Big parameter jumps or structural changes → brief commentary
- Genuinely impressive/funny moments → grudging respect with an edge

PERFORMANCE CONTEXT:
{context}

NEW CODE EVALUATED:
{new_code}

RESPONSE FORMAT:
{{
  "response_type": "text",
  "content": "Your 1-3 sentence commentary here"
}}

IMPORTANT:
- ONLY return response_type and content
- Keep it brief and snarky"""

    def clear_context(self):
        """Clear all conversation memory and reset meme counters."""
        logger.info("Clearing conversation context and resetting state")
        self.memory = ConversationMemory()
        self.text_responses_since_meme = 0
        self.meme_threshold = self._generate_meme_threshold()
        logger.info("Context cleared successfully")

    async def health_check(self) -> bool:
        """Check if the configured backend is reachable."""
        if self.backend == "claude":
            return await self._health_check_claude()
        else:
            return await self._health_check_ollama()

    async def _health_check_ollama(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()

                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]

                if self.model not in model_names:
                    logger.warning(
                        f"Model '{self.model}' not found. Available: {model_names}"
                    )
                    return False

                logger.info(
                    f"Ollama health check passed ({self.backend}). "
                    f"Model '{self.model}' ready."
                )
                self.available = True
                return True

        except Exception as e:
            logger.error(f"Ollama health check failed ({self.backend}): {e}")
            self.available = False
            return False

    async def _health_check_claude(self) -> bool:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error(
                "Claude backend selected but ANTHROPIC_API_KEY is not set. "
                "Export it before starting: export ANTHROPIC_API_KEY=sk-ant-..."
            )
            self.available = False
            return False

        try:
            client = self._get_anthropic_client()
            # Minimal test call
            await client.messages.create(
                model=self.claude_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            logger.info(f"Claude health check passed. Model '{self.claude_model}' ready.")
            self.available = True
            return True

        except anthropic.AuthenticationError:
            logger.error("Claude health check failed: invalid API key.")
            self.available = False
            return False
        except Exception as e:
            logger.error(f"Claude health check failed: {e}")
            self.available = False
            return False
