"""
LLM integration module for Ollama with context management.

This module handles:
- Communication with Ollama API
- Context window management (sliding window + salience markers)
- Public vs private LLM requests
- Memory compression and summarization
"""

import logging
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
        # Heuristics for musical importance
        salient_keywords = ["Ndef", "Pdef", "Tdef", "SynthDef", "play", "clear", "stop"]
        return any(keyword in self.code for keyword in salient_keywords)


@dataclass
class ConversationMemory:
    """Manages LLM context with temporal awareness."""

    # Configuration
    max_recent_blocks: int = 5  # Keep this many blocks in full detail
    max_total_blocks: int = 20  # Total history to maintain

    # Storage
    blocks: deque[CodeBlock] = field(default_factory=deque)
    summaries: list[str] = field(default_factory=list)  # Private summaries

    def add_block(self, code: str) -> CodeBlock:
        """Add a new code block to memory."""
        block = CodeBlock(
            code=code,
            timestamp=datetime.now(),
            salience=1 if self._is_salient(code) else 0,
        )

        self.blocks.append(block)

        # Trim old blocks if we exceed max_total_blocks
        if len(self.blocks) > self.max_total_blocks:
            self.blocks.popleft()

        return block

    def _is_salient(self, code: str) -> bool:
        """Determine if code block is musically important."""
        salient_keywords = ["Ndef", "Pdef", "Tdef", "SynthDef", "play", "clear", "stop"]
        # Check for big parameter changes
        has_large_numbers = any(
            token.replace(".", "").isdigit() and float(token) > 100
            for token in code.split()
            if token.replace(".", "").replace("-", "").isdigit()
        )
        return any(keyword in code for keyword in salient_keywords) or has_large_numbers

    def get_context_prompt(self) -> str:
        """
        Build context prompt for LLM with weighted recency.

        Recent blocks get full text, older ones get compressed summaries.
        Salient blocks persist longer in full detail.
        """
        if not self.blocks:
            return "No previous code has been evaluated yet."

        context_parts = []

        # Add any accumulated summaries
        if self.summaries:
            context_parts.append("## Performance History Summary")
            context_parts.extend(self.summaries)
            context_parts.append("")

        # Recent blocks in detail
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

    async def compress_history(self, ollama_client: "OllamaClient") -> str:
        """
        Create a private summary of older blocks (not displayed to audience).

        This is a "hidden" LLM request that compresses musical trajectory.
        """
        if len(self.blocks) < self.max_recent_blocks:
            return ""

        # Get blocks that are beyond the recent window
        old_blocks = list(self.blocks)[: -self.max_recent_blocks]
        if not old_blocks:
            return ""

        codes = "\n\n".join(f"Block {i}: {b.code}" for i, b in enumerate(old_blocks, 1))

        summary = await ollama_client.request_private_summary(codes)
        self.summaries.append(summary)

        # Clear compressed blocks
        for _ in range(len(old_blocks)):
            if len(self.blocks) > self.max_recent_blocks:
                self.blocks.popleft()

        return summary


class OllamaClient:
    """
    Client for Ollama LLM API with structured output support.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        model: str = "llama3.1:8b",
        temperature: float = 0.8,
        timeout: float = 30.0,
        meme_min_interval: int = 5,
        meme_max_interval: int = 10,
    ):
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.memory = ConversationMemory()
        self.ollama_available = False  # Track Ollama availability

        # Meme generation state management
        self.meme_min_interval = meme_min_interval
        self.meme_max_interval = meme_max_interval
        self.text_responses_since_meme = 0
        self.meme_threshold = self._generate_meme_threshold()

        # Available MemePy templates with arg counts
        # Ordered by arg count to reduce bias
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

    def _generate_meme_threshold(self) -> int:
        """Generate a random threshold for when to request next meme."""
        return self.meme_min_interval + random.randint(
            0, self.meme_max_interval - self.meme_min_interval
        )

    def _validate_meme_args(self, response: MemeResponse) -> tuple[bool, str]:
        """
        Validate that meme response has correct number of args for template.

        Returns (is_valid, error_message).
        """
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

    async def generate_commentary(self, code: str) -> Response:
        """
        Generate public LLM commentary for evaluated code (displayed to audience).

        Returns either text commentary or a meme response.
        """
        # Add to memory
        self.memory.add_block(code)
        context = self.memory.get_context_prompt()

        # If Ollama is unavailable, return mock response
        if not self.ollama_available:
            logger.debug("Using mock LLM response (Ollama unavailable)")
            return TextResponse(
                response_type="text",
                content=f"[Mock LLM] Received code: {code[:50]}...",
            )

        # Determine if we should request a meme or text response
        should_request_meme = self.text_responses_since_meme >= self.meme_threshold
        logger.info(
            f"Response decision: text_count={self.text_responses_since_meme}, "
            f"threshold={self.meme_threshold}, requesting_meme={should_request_meme}"
        )

        # Build prompt with mode hint
        prompt = self._build_commentary_prompt(
            context, code, request_meme=should_request_meme
        )

        # Define response schema with oneOf for proper discrimination
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
                response_text = result["response"]

                # Parse JSON response
                import json

                parsed: Response = json.loads(response_text)

                # Validate meme responses and retry once if invalid
                if parsed["response_type"] == "meme":
                    is_valid, error_msg = self._validate_meme_args(parsed)
                    if not is_valid:
                        logger.warning(f"Invalid meme response: {error_msg}")
                        logger.info("Retrying with error feedback...")

                        # Retry once with error message in prompt
                        retry_prompt = f"""{prompt}

ERROR FROM PREVIOUS ATTEMPT:
{error_msg}

Please try again, ensuring you provide the correct number of arguments."""

                        try:
                            retry_response = await client.post(
                                f"{self.base_url}/api/generate",
                                json={
                                    "model": self.model,
                                    "prompt": retry_prompt,
                                    "stream": False,
                                    "format": schema,
                                    "options": {
                                        "temperature": self.temperature,
                                        "num_ctx": 4096,
                                    },
                                },
                            )
                            retry_response.raise_for_status()
                            retry_result = retry_response.json()
                            retry_text = retry_result["response"]
                            parsed = json.loads(retry_text)

                            # Validate retry
                            if parsed["response_type"] == "meme":
                                is_valid_retry, error_msg_retry = (
                                    self._validate_meme_args(parsed)
                                )
                                if not is_valid_retry:
                                    logger.error(
                                        f"Retry also failed: {error_msg_retry}"
                                    )
                                    # Fall back to text response
                                    return TextResponse(
                                        response_type="text",
                                        content="[Meme generation failed - arg count mismatch]",
                                    )
                            logger.info("Retry successful!")

                        except Exception as retry_err:
                            logger.error(f"Retry failed: {retry_err}")
                            return TextResponse(
                                response_type="text",
                                content="[Meme retry failed]",
                            )

                # Update meme/text counter based on response type
                if parsed["response_type"] == "meme":
                    # Reset counter and generate new threshold
                    self.text_responses_since_meme = 0
                    self.meme_threshold = self._generate_meme_threshold()
                    logger.info(
                        f"Meme generated. Reset counter. New threshold: {self.meme_threshold}"
                    )
                else:
                    # Increment text response counter
                    self.text_responses_since_meme += 1
                    logger.debug(
                        f"Text response. Counter: {self.text_responses_since_meme}/{self.meme_threshold}"
                    )

                logger.info(f"LLM response: {parsed}")
                return parsed

        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            # Increment counter even on error (it was a text attempt)
            self.text_responses_since_meme += 1
            # Fallback response
            return TextResponse(response_type="text", content=f"[LLM Error: {e}]")

    async def request_private_summary(self, old_codes: str) -> str:
        """
        Request a private summary (not displayed to audience).

        Used for context compression.
        """
        prompt = f"""You are summarizing a live coding performance for internal memory management.
Compress these older SuperCollider code evaluations into a brief musical trajectory summary.
Focus on: key patterns established, synthesis techniques used, structural changes.

OLD CODE BLOCKS:
{old_codes}

Provide a 2-3 sentence summary of the musical direction so far:"""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.5,  # Lower temp for summaries
                            "num_ctx": 4096,
                        },
                    },
                )
                response.raise_for_status()

                result = response.json()
                return result["response"]

        except Exception as e:
            logger.error(f"Private summary failed: {e}")
            return "[Summary unavailable]"

    def _build_commentary_prompt(
        self, context: str, new_code: str, request_meme: bool = False
    ) -> str:
        """Build the prompt for public commentary."""
        # Import meme metadata from memes.py
        from . import memes

        template_info = memes.get_meme_metadata_for_llm()

        # Use completely different prompt when requesting meme
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

        # Text response prompt (original)
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
        """
        Clear all conversation memory and reset meme counters.

        Use this before starting a new performance to avoid reactions
        to previous session's context.
        """
        logger.info("Clearing conversation context and resetting state")
        self.memory = ConversationMemory()
        self.text_responses_since_meme = 0
        self.meme_threshold = self._generate_meme_threshold()
        logger.info("Context cleared successfully")

    async def health_check(self) -> bool:
        """Check if Ollama server is reachable and model is available."""
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

                logger.info(f"Ollama health check passed. Model '{self.model}' ready.")
                self.ollama_available = True
                return True

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            self.ollama_available = False
            return False
