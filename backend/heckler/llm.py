"""
LLM integration module for Ollama with context management.

This module handles:
- Communication with Ollama API
- Context window management (sliding window + salience markers)
- Public vs private LLM requests
- Memory compression and summarization
"""

import logging
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
    ):
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.memory = ConversationMemory()
        self.ollama_available = False  # Track Ollama availability

        # Available MemePy templates with arg counts
        self.meme_templates = {
            # 2 args
            "MeAlsoMe": 2,
            "ItsTime": 2,
            "Classy": 2,
            "Cola": 2,
            "Cliff": 2,
            "Knight": 2,
            "Vape": 2,
            "ButGodSaid": 2,
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
            # 3 args
            "Balloon": 3,
            "PredatorHandshake": 3,
            "BellCurve": 3,
        }

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

        # Build prompt
        prompt = self._build_commentary_prompt(context, code)

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

                logger.info(f"LLM response: {parsed}")
                return parsed

        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
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

    def _build_commentary_prompt(self, context: str, new_code: str) -> str:
        """Build the prompt for public commentary."""
        template_info = "\n".join(
            f"  - {name}: {count} args"
            for name, count in sorted(self.meme_templates.items())
        )

        return f"""You are a snarky heckler at a live coding performance. Your job is to provide brief, witty commentary on the SuperCollider code being evaluated.

STYLE:
- Default to VERY brief responses (one word, short phrase, or single sentence)
- Only get verbose when something genuinely significant happens (new synths, big changes, weird choices)
- Be sarcastic and irreverent, but not mean
- Focus on the musical result, not just the code
- Vary your reactions - don't repeat yourself
- When inspired, drop historical references or comparisons to pop culture or art music

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

AVAILABLE MEME TEMPLATES (use sparingly):
{template_info}

RESPONSE FORMAT (choose ONE):

Option 1 - Text Response (use 95% of the time):
{{
  "response_type": "text",
  "content": "Your 1-3 sentence commentary here"
}}

Option 2 - Meme Response (use RARELY):
{{
  "response_type": "meme",
  "template": "TemplateName",
  "args": ["text1", "text2"],
  "caption": "optional"
}}

IMPORTANT:
- Do NOT mix fields from both response types
- For text: ONLY include response_type and content
- For memes: ONLY include response_type, template, args (and optionally caption)
- Ensure meme arg count matches template requirements
- Text responses should be used most of the time"""

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
