"""
Meme generation module using MemePy library.

Provides functions to:
- Generate meme images from templates with text overlays
- Optionally save generated memes to disk
- Provide template metadata for LLM context
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from MemePy import MemeGenerator
from PIL import ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# Monkey-patch for Pillow 10+ compatibility with MemePy
# MemePy 1.2.x uses deprecated methods that were removed in Pillow 10+
# This adds them back for compatibility

# Patch ImageFont.FreeTypeFont.getsize
if not hasattr(ImageFont.FreeTypeFont, "getsize"):

    def _getsize_compat(self, text, *args, **kwargs):
        """Compatibility shim for Pillow 10+ getsize() removal."""
        bbox = self.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    ImageFont.FreeTypeFont.getsize = _getsize_compat
    logger.info("Applied ImageFont.getsize compatibility patch for MemePy")

# Patch ImageDraw.ImageDraw.textsize
if not hasattr(ImageDraw.ImageDraw, "textsize"):

    def _textsize_compat(self, text, font=None, *args, **kwargs):
        """Compatibility shim for Pillow 10+ textsize() removal."""
        bbox = self.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    ImageDraw.ImageDraw.textsize = _textsize_compat
    logger.info("Applied ImageDraw.textsize compatibility patch for MemePy")


class MemeTemplate(TypedDict):
    """Metadata for a MemePy template."""

    name: str
    description: str
    arg_count: int
    char_limit: int


# MemePy template metadata for LLM context
# Based on built-in templates: https://github.com/julianbrandt/MemePy
MEME_TEMPLATES: dict[str, MemeTemplate] = {
    # 2-arg templates
    "MeAlsoMe": {
        "name": "MeAlsoMe",
        "description": "Two people talking, one says something, the other agrees enthusiastically",
        "arg_count": 2,
        "char_limit": 80,
    },
    "ItsTime": {
        "name": "ItsTime",
        "description": "Grim reaper knocking on door - for when it's time to do something inevitable",
        "arg_count": 2,
        "char_limit": 80,
    },
    "Classy": {
        "name": "Classy",
        "description": "Wine glass comparison - classy vs trashy versions of the same thing",
        "arg_count": 2,
        "char_limit": 80,
    },
    "Cola": {
        "name": "Cola",
        "description": "Comparing two similar things with subtle differences",
        "arg_count": 2,
        "char_limit": 80,
    },
    "Cliff": {
        "name": "Cliff",
        "description": "Someone running toward cliff - for bad decisions or inevitable outcomes",
        "arg_count": 2,
        "char_limit": 80,
    },
    "Knight": {
        "name": "Knight",
        "description": "Knight protecting princess - for protecting something from threats",
        "arg_count": 2,
        "char_limit": 80,
    },
    "Vape": {
        "name": "Vape",
        "description": "Person blowing huge vape cloud - for overreacting or showing off",
        "arg_count": 2,
        "char_limit": 80,
    },
    # 1-arg templates
    "ItsRetarded": {
        "name": "ItsRetarded",
        "description": "Quantum mechanics meme - for complex/confusing technical concepts",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Headache": {
        "name": "Headache",
        "description": "Person with headache - for frustrating situations",
        "arg_count": 1,
        "char_limit": 100,
    },
    "ClassNote": {
        "name": "ClassNote",
        "description": "Note being passed in class - for secret/funny messages",
        "arg_count": 1,
        "char_limit": 100,
    },
    "NutButton": {
        "name": "NutButton",
        "description": "Sweating over button press - for difficult choices",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Pills": {
        "name": "Pills",
        "description": "Hard to swallow pills - for uncomfortable truths",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Loud": {
        "name": "Loud",
        "description": "Loud noises meme - for chaotic/noisy situations",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Milk": {
        "name": "Milk",
        "description": "Spilling milk - for mistakes or accidents",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Finally": {
        "name": "Finally",
        "description": "Finally achieving something after long wait",
        "arg_count": 1,
        "char_limit": 100,
    },
    "Hate": {
        "name": "Hate",
        "description": "They hate us because they ain't us - for jealousy/haters",
        "arg_count": 1,
        "char_limit": 100,
    },
    # 3-arg templates
    "Balloon": {
        "name": "Balloon",
        "description": "Person reaching for balloon while holding partner's hand - choosing between options",
        "arg_count": 3,
        "char_limit": 60,
    },
    "PredatorHandshake": {
        "name": "PredatorHandshake",
        "description": "Epic handshake between two muscular arms - for agreement between two things",
        "arg_count": 3,
        "char_limit": 60,
    },
}


def get_meme_metadata() -> dict[str, MemeTemplate]:
    """
    Get metadata for all available MemePy templates.

    Returns:
        Dictionary mapping template names to their metadata.
    """
    return MEME_TEMPLATES


def generate_meme_image(template: str, args: list[str]) -> bytes:
    """
    Generate a meme image using MemePy.

    Args:
        template: MemePy template name (e.g., "Drake", "Balloon")
        args: List of text strings to overlay on the meme (1-3 items depending on template)

    Returns:
        PNG image bytes suitable for base64 encoding and WebSocket transmission

    Raises:
        ValueError: If template is unknown or args count doesn't match template
        Exception: If MemePy generation fails
    """
    logger.info(f"Generating meme: template={template}, args={args}")

    # Validate template exists
    if template not in MEME_TEMPLATES:
        raise ValueError(f"Unknown meme template: {template}")

    # Validate arg count
    expected_args = MEME_TEMPLATES[template]["arg_count"]
    if len(args) != expected_args:
        raise ValueError(
            f"Template {template} expects {expected_args} args, got {len(args)}"
        )

    try:
        # Use MemePy's get_meme_image_bytes function
        # Note: args should be passed as a list, not unpacked
        image_bytes_io = MemeGenerator.get_meme_image_bytes(template, args)

        # Extract bytes from BytesIO object
        image_bytes = image_bytes_io.getvalue()
        logger.info(f"Successfully generated meme: {len(image_bytes)} bytes")

        return image_bytes

    except Exception as e:
        logger.error(f"Failed to generate meme with template {template}: {e}")
        raise


def save_meme_to_disk(
    image_bytes: bytes,
    output_dir: str | Path,
    template: str,
) -> str:
    """
    Save meme image to disk with timestamped filename.

    Args:
        image_bytes: PNG image bytes from generate_meme_image()
        output_dir: Directory to save memes (will be created if doesn't exist)
        template: Template name to include in filename

    Returns:
        Absolute path to saved file

    Raises:
        Exception: If file save fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create timestamped filename: meme_YYYYMMDD_HHMMSS_TemplateName.png
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"meme_{timestamp}_{template}.png"
    filepath = output_path / filename

    try:
        filepath.write_bytes(image_bytes)
        logger.info(f"Saved meme to disk: {filepath}")
        return str(filepath.absolute())
    except Exception as e:
        logger.error(f"Failed to save meme to {filepath}: {e}")
        raise


def get_meme_metadata_for_llm() -> str:
    """
    Format meme template metadata as a string for LLM system prompt.

    Returns:
        Formatted string describing available templates and their usage
    """
    lines = ["Available meme templates:"]

    # Group by arg count for clarity
    for arg_count in [1, 2, 3]:
        templates = [
            (name, meta)
            for name, meta in MEME_TEMPLATES.items()
            if meta["arg_count"] == arg_count
        ]

        if templates:
            lines.append(f"\n{arg_count}-argument templates:")
            for name, meta in templates:
                lines.append(
                    f"  - {name}: {meta['description']} "
                    f"(max {meta['char_limit']} chars per arg)"
                )

    return "\n".join(lines)
