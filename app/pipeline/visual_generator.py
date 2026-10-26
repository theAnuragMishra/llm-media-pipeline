"""Visual slide and scene renderer using Pillow for high-definition 1080p composition."""

import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.models.schemas import ScriptScene

logger = logging.getLogger(__name__)


class VisualGenerator:
    """Renders sleek 1920x1080 educational slides for each scene in the storyboard."""

    def __init__(self):
        self.width = 1920
        self.height = 1080

    def render_scene_slide(
        self,
        scene: ScriptScene,
        total_scenes: int,
        topic: str,
        output_path: Path,
    ) -> Path:
        """Draws a complete 1080p presentation slide for the given scene."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", (self.width, self.height), color=(15, 23, 42, 255)) # Dark slate base
        draw = ImageDraw.Draw(img)

        # 1. Subtle gradient backdrop
        for y in range(self.height):
            ratio = y / self.height
            r = int(15 + ratio * (24 - 15))
            g = int(23 + ratio * (24 - 23))
            b = int(42 + ratio * (70 - 42))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b, 255))

        # 2. Tech accent lines and subtle border
        draw.line([(80, 100), (self.width - 80, 100)], fill=(51, 65, 85, 180), width=2)
        draw.rectangle([(60, 60), (self.width - 60, self.height - 60)], outline=(30, 41, 59, 200), width=2)

        # 3. Load Fonts (standard system fonts with safe fallbacks)
        font_title = self._get_font(size=56, bold=True)
        font_header_tag = self._get_font(size=24, bold=True)
        font_body = self._get_font(size=36, bold=False)
        font_concept = self._get_font(size=28, bold=True)
        font_code = self._get_font(size=30, bold=False)

        # 4. Top Tag / Badge
        badge_text = f"MODULE // SCENE {scene.scene_number} OF {total_scenes} • {topic.upper()}"
        draw.rounded_rectangle([(80, 50), (620, 88)], radius=8, fill=(30, 41, 59, 230), outline=(56, 189, 248, 180))
        draw.text((100, 56), badge_text, fill=(56, 189, 248, 255), font=font_header_tag)

        # 5. Slide Title
        draw.text((80, 130), scene.title, fill=(248, 250, 252, 255), font=font_title)

        # 6. Bullet Points Section (Left Column)
        bullet_start_y = 240
        for i, point in enumerate(scene.bullet_points):
            y_pos = bullet_start_y + (i * 90)
            # Glowing bullet icon
            draw.rounded_rectangle([(80, y_pos + 6), (96, y_pos + 22)], radius=4, fill=(14, 165, 233, 255))
            # Text
            wrapped_text = self._wrap_text(point, max_chars=48)
            draw.text((120, y_pos), wrapped_text, fill=(226, 232, 240, 255), font=font_body)

        # 7. Right Column Cards: Key Concept & Formula/Code Box
        card_x = 1100
        card_w = 740

        # Concept Card
        if scene.key_concept:
            draw.rounded_rectangle(
                [(card_x, 240), (card_x + card_w, 360)],
                radius=14,
                fill=(30, 41, 59, 220),
                outline=(99, 102, 241, 200),
                width=2,
            )
            draw.text((card_x + 30, 260), "KEY TAKEAWAY", fill=(129, 140, 248, 255), font=font_header_tag)
            draw.text((card_x + 30, 298), scene.key_concept, fill=(255, 255, 255, 255), font=font_concept)

        # Code / Formula Card
        if scene.code_or_formula:
            draw.rounded_rectangle(
                [(card_x, 400), (card_x + card_w, 620)],
                radius=14,
                fill=(15, 23, 42, 240),
                outline=(51, 65, 85, 220),
                width=2,
            )
            # Window header circles (macOS style window buttons)
            draw.ellipse([(card_x + 25, 420), (card_x + 37, 432)], fill=(239, 68, 68, 220))
            draw.ellipse([(card_x + 45, 420), (card_x + 57, 432)], fill=(245, 158, 11, 220))
            draw.ellipse([(card_x + 65, 420), (card_x + 77, 432)], fill=(34, 197, 94, 220))
            draw.line([(card_x, 448), (card_x + card_w, 448)], fill=(30, 41, 59, 200), width=1)

            # Formula text
            lines = scene.code_or_formula.split("\n")
            for j, line in enumerate(lines[:4]):
                draw.text((card_x + 30, 475 + (j * 40)), line, fill=(56, 189, 248, 255), font=font_code)

        # 8. Bottom Timeline / Scene Progress Indicator
        timeline_y = self.height - 100
        step_width = (self.width - 200) / total_scenes
        for s in range(total_scenes):
            step_x = 100 + s * step_width
            is_active = (s + 1) <= scene.scene_number
            color = (14, 165, 233, 255) if is_active else (51, 65, 85, 180)
            draw.rounded_rectangle([(step_x, timeline_y), (step_x + step_width - 20, timeline_y + 8)], radius=4, fill=color)

        # Save to disk
        img.save(str(output_path), "PNG")
        scene.slide_image_path = str(output_path)
        logger.info("Rendered slide image: %s", output_path)
        return output_path

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        """Attempt to load clean system TTF fonts, fallback to default."""
        font_candidates = [
            "/System/Library/Fonts/SFPro.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in font_candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _wrap_text(self, text: str, max_chars: int) -> str:
        """Basic word wrap helper for slide text layout."""
        words = text.split()
        lines = []
        current_line = []
        current_len = 0

        for w in words:
            if current_len + len(w) + 1 > max_chars:
                lines.append(" ".join(current_line))
                current_line = [w]
                current_len = len(w)
            else:
                current_line.append(w)
                current_len += len(w) + 1

        if current_line:
            lines.append(" ".join(current_line))

        return "\n  ".join(lines)


visual_generator = VisualGenerator()
