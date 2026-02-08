"""Image Generator agent -- generates per-section images for articles.

This agent runs after the EDIT step. It parses the article markdown,
identifies H2 sections, checks for matching knowledge base images,
and generates new images via DALL-E for sections without matching images.
It then inserts image markdown references into the article.
"""

from __future__ import annotations

import re
import time
from typing import Any

import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import settings

logger = structlog.get_logger(__name__)


class ImageGeneratorAgent(BaseAgent):
    """Generates and inserts images into article markdown."""

    @property
    def agent_name(self) -> str:
        return "image_generator"

    @property
    def model_name(self) -> str:
        return settings.default_orchestrator_model  # Haiku for speed

    @property
    def system_prompt(self) -> str:
        return (
            "You are an image selection and prompt generation specialist for "
            "knock knock AI's content marketing platform. Your job is to select "
            "the most appropriate existing images from the knowledge base or "
            "generate DALL-E prompts for new images that complement each article section."
        )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate images for each article section.

        Expected input_data keys:
        - edit (dict): Contains 'edited_markdown' or 'article_markdown'
        - calendar_entry (dict): Article metadata
        - knowledge_images (list): Available knowledge base images with tags

        Returns output_data with:
        - article_markdown (str): Updated markdown with image references
        - generated_images (list): List of generated image metadata
        - matched_kb_images (list): List of knowledge base images matched
        """
        self._reset_token_tracking()
        start = time.monotonic()

        cal = context.input_data.get("calendar_entry", {})
        edit_data = context.input_data.get("edit", {})
        article_md = (
            edit_data.get("edited_markdown")
            or edit_data.get("article_markdown")
            or context.input_data.get("write", {}).get("article_markdown", "")
        )
        topic = cal.get("topic", "")
        language = cal.get("language", "ja")
        kb_images: list[dict[str, Any]] = context.input_data.get("knowledge_images", [])

        if not article_md:
            return AgentResult(
                success=False,
                error_message="No article markdown found in input data.",
                execution_time_seconds=time.monotonic() - start,
            )

        # Parse sections from article
        sections = self._parse_sections(article_md)
        self._log.info("image_gen_sections_found", count=len(sections))

        generated_images: list[dict[str, Any]] = []
        matched_kb_images: list[dict[str, Any]] = []

        # For each section, try to match a KB image or generate one
        for section in sections:
            heading = section["heading"]
            content = section["content"]

            # Check knowledge base images first
            kb_match = self._find_matching_kb_image(heading, content, kb_images)
            if kb_match:
                matched_kb_images.append({
                    "section_heading": heading,
                    "image_id": kb_match["id"],
                    "filename": kb_match["filename"],
                    "tags": kb_match.get("tags", []),
                })
                # Insert image reference after the heading
                image_ref = f"\n\n![{kb_match.get('description', heading)}](/api/v1/images/{kb_match['id']}/file)\n"
                article_md = article_md.replace(
                    heading,
                    heading + image_ref,
                    1,
                )
                continue

            # Generate a new image via DALL-E
            try:
                from app.services.image_generator import (
                    build_section_image_prompt,
                    generate_image,
                )

                prompt = build_section_image_prompt(heading, content, topic, language)

                # Use LLM to refine the prompt for better results
                refined_prompt = await self._refine_prompt(prompt, heading, topic)

                image_result = await generate_image(
                    refined_prompt,
                    size="1792x1024",
                    quality="standard",
                )

                # Auto-generate tags from the section content
                tags = self._extract_tags(heading, content, topic)

                generated_images.append({
                    "section_heading": heading,
                    "prompt": refined_prompt,
                    "filename": image_result.filename,
                    "file_path": image_result.file_path,
                    "width": image_result.width,
                    "height": image_result.height,
                    "file_size": image_result.file_size,
                    "tags": tags,
                })

                # We'll insert the image reference after saving to DB (in the service layer)
                # For now, mark where images should go
                image_placeholder = f"\n\n![{heading}]({{IMAGE_PLACEHOLDER:{image_result.filename}}})\n"
                article_md = article_md.replace(
                    heading,
                    heading + image_placeholder,
                    1,
                )

            except Exception as exc:
                self._log.warning(
                    "image_generation_failed",
                    section=heading,
                    error=str(exc),
                )
                # Continue without image for this section

        elapsed = time.monotonic() - start
        self._log.info(
            "image_gen_complete",
            generated=len(generated_images),
            matched_kb=len(matched_kb_images),
            elapsed=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data={
                "article_markdown": article_md,
                "generated_images": generated_images,
                "matched_kb_images": matched_kb_images,
            },
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=elapsed,
        )

    async def _refine_prompt(self, base_prompt: str, heading: str, topic: str) -> str:
        """Use LLM to create a better DALL-E prompt."""
        try:
            response = await self._call_llm(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Create a concise, effective DALL-E 3 image generation prompt "
                        f"for a blog article section.\n\n"
                        f"Article topic: {topic}\n"
                        f"Section heading: {heading}\n"
                        f"Base prompt: {base_prompt}\n\n"
                        f"Requirements:\n"
                        f"- Professional, modern blog image\n"
                        f"- No text or words in the image\n"
                        f"- Suitable for real estate / PropTech content\n"
                        f"- Clean, minimalist style\n\n"
                        f"Return ONLY the refined prompt text, nothing else."
                    ),
                }],
                max_tokens=300,
                temperature=0.7,
            )
            refined = self._text_from_response(response).strip()
            return refined[:1000] if refined else base_prompt
        except Exception:
            return base_prompt

    @staticmethod
    def _parse_sections(markdown: str) -> list[dict[str, str]]:
        """Parse markdown into sections based on H2 headings."""
        sections: list[dict[str, str]] = []
        parts = re.split(r"(^## .+$)", markdown, flags=re.MULTILINE)

        current_heading = ""
        current_content = ""
        for part in parts:
            if part.startswith("## "):
                if current_heading:
                    sections.append({
                        "heading": current_heading,
                        "content": current_content.strip(),
                    })
                current_heading = part.strip()
                current_content = ""
            else:
                current_content += part

        if current_heading:
            sections.append({
                "heading": current_heading,
                "content": current_content.strip(),
            })

        return sections

    @staticmethod
    def _find_matching_kb_image(
        heading: str,
        content: str,
        kb_images: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Find a knowledge base image whose tags match the section content."""
        if not kb_images:
            return None

        heading_lower = heading.lower()
        content_lower = content[:500].lower()
        search_text = heading_lower + " " + content_lower

        best_match = None
        best_score = 0

        for img in kb_images:
            tags = img.get("tags", []) or []
            if not tags:
                continue

            score = 0
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in search_text:
                    score += 2
                # Partial word match
                for word in tag_lower.split():
                    if word in search_text and len(word) > 2:
                        score += 1

            if score > best_score:
                best_score = score
                best_match = img

        # Only return a match if score is significant enough
        if best_score >= 2 and best_match:
            return best_match
        return None

    @staticmethod
    def _extract_tags(heading: str, content: str, topic: str) -> list[str]:
        """Extract tags from section content for auto-tagging generated images."""
        tags: list[str] = []

        # Add topic as a tag
        if topic:
            tags.append(topic)

        # Extract key words from heading
        heading_clean = re.sub(r"^#+\s*", "", heading)
        if heading_clean:
            tags.append(heading_clean)

        # Extract notable terms from content (words in bold)
        bold_terms = re.findall(r"\*\*(.+?)\*\*", content[:1000])
        for term in bold_terms[:5]:
            if term not in tags and len(term) < 50:
                tags.append(term)

        return tags[:8]  # Limit to 8 tags
