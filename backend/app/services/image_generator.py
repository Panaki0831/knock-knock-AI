"""Image generation service -- generates images via OpenAI DALL-E API."""

from __future__ import annotations

import base64
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Directory where images are stored
MEDIA_DIR = Path("/app/media/images")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class GeneratedImage:
    """Result of an image generation request."""

    file_path: str
    filename: str
    prompt: str
    width: int
    height: int
    file_size: int


async def generate_image(
    prompt: str,
    *,
    size: str = "1792x1024",
    quality: str = "standard",
    style: str = "natural",
) -> GeneratedImage:
    """Generate an image using OpenAI DALL-E 3.

    Args:
        prompt: The image generation prompt.
        size: Image dimensions (1024x1024, 1792x1024, 1024x1792).
        quality: "standard" or "hd".
        style: "natural" or "vivid".

    Returns:
        A GeneratedImage with the file path and metadata.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key not configured -- cannot generate images")

    log = logger.bind(component="image_generator")
    log.info("generating_image", prompt=prompt[:100], size=size)

    start = time.monotonic()

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": quality,
                "style": style,
                "response_format": "b64_json",
            },
        )
        resp.raise_for_status()

    data = resp.json()
    b64_data = data["data"][0]["b64_json"]
    image_bytes = base64.b64decode(b64_data)

    # Parse dimensions
    w, h = (int(x) for x in size.split("x"))

    # Save to disk
    filename = f"{uuid.uuid4().hex}.png"
    file_path = MEDIA_DIR / filename
    file_path.write_bytes(image_bytes)

    elapsed = time.monotonic() - start
    log.info(
        "image_generated",
        filename=filename,
        size_bytes=len(image_bytes),
        elapsed_seconds=round(elapsed, 2),
    )

    return GeneratedImage(
        file_path=str(file_path),
        filename=filename,
        prompt=prompt,
        width=w,
        height=h,
        file_size=len(image_bytes),
    )


def build_section_image_prompt(
    section_heading: str,
    section_content: str,
    article_topic: str,
    language: str = "ja",
) -> str:
    """Build an optimized DALL-E prompt for a specific article section.

    Creates a descriptive prompt that generates a relevant, professional
    blog image for the given section content.
    """
    # Extract key concepts from section content (first ~200 chars)
    content_preview = section_content[:300].replace("\n", " ")

    prompt = (
        f"A professional, modern blog header image for an article about "
        f"'{article_topic}'. This specific section covers: '{section_heading}'. "
        f"Context: {content_preview}. "
        f"Style: Clean, minimalist design with soft gradients. "
        f"Professional and corporate feel suitable for a real estate / PropTech "
        f"technology blog. No text or words in the image. "
        f"High quality, photorealistic or modern illustration style."
    )
    return prompt[:1000]  # DALL-E prompt limit


def save_uploaded_image(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """Save an uploaded image file to the media directory.

    Returns (file_path, stored_filename).
    """
    ext = Path(filename).suffix.lower() or ".png"
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = MEDIA_DIR / stored_name
    file_path.write_bytes(file_bytes)
    return str(file_path), stored_name
