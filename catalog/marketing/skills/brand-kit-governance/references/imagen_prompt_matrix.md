# Imagen Multi-Format Prompt Matrix (`1:1`, `16:9`, `9:16`)

Use this matrix when constructing prompts for the Gemini Enterprise **Imagen** image generation tool so every marketing visual matches channel dimensions, safe zones, and brand fidelity.

---

## 1. Aspect Ratio & Channel Specification Matrix

| Aspect Ratio | Primary Marketing Channels | Framing & Subject Placement | Post-Production Copy Safe Zone |
| :--- | :--- | :--- | :--- |
| **`1:1` (Square)** | LinkedIn Feed, Instagram Feed, Paid Carousel Cards | Centered or rule-of-thirds hero subject (`60%` frame weight); balanced breathing room around edges. | Top `20%` or bottom `22%` clean gradient/negative space for headline badge or lower-third CTA. |
| **`16:9` (Widescreen)** | Website Hero Banners, YouTube Thumbnails, Event Keynotes, Blog Headers | Asymmetric left-or-right thirds subject placement; wide environmental storytelling context. | Keep left `38%` (or right `38%`) uncluttered low-contrast negative space for headline, subhead, and CTA button. |
| **`9:16` (Vertical)** | Instagram Stories/Reels Cover, YouTube Shorts, TikTok, Mobile Interstitials | Vertical center-weighted subject (`middle 50%` of frame) with strong vertical leading lines. | Keep top `15%` (platform UI header) and bottom `25%` (caption/CTA drawer) free of critical subject details. |

---

## 2. 6-Part Imagen Prompt Formula

Assemble every Imagen prompt in this exact order before invoking the image generation tool:

1. **Format & Medium:** Editorial commercial photograph / precision 3D studio render, `[1:1 | 16:9 | 9:16]` composition.
2. **Primary Subject:** Concrete, unambiguous description of the person, product artifact, or visual metaphor.
3. **Environment & Setting:** Architectural space, workspace, or studio backdrop grounded in brand palette surfaces.
4. **Lighting & Color Mood:** Natural-language translation of brand palette tokens (e.g., *warm key light with subtle sky-cyan rim accent against matte slate*).
5. **Camera & Lens Optics:** Focal length, aperture, and angle (e.g., *50mm lens, f/2.2, eye-level perspective, crisp micro-contrast*).
6. **Negative Space & Exclusions:** Explicit uncluttered zone for overlay typography; *no text, no watermarks, no logos, no cluttered background screens*.

---

## 3. Ready-to-Adapt Prompt Archetypes

### Archetype A — `16:9` Product Launch Web Hero
> Editorial commercial studio render in widescreen 16:9 composition, sleek translucent optical glass prism refracting a clean beam of sky-cyan and mint-teal light on the right third of the frame, resting on a matte dark slate architectural surface. Left forty percent of the frame features smooth, uncluttered deep obsidian negative space for headline placement. Soft studio rim lighting, 85mm macro lens, f/2.8, ultra-clean minimalist enterprise aesthetic, no text, no logos, no watermarks.

### Archetype B — `1:1` Customer Outcome Social Card
> Authentic editorial photograph in square 1:1 composition, two diverse marketing strategists collaborating at a modern sunlit timber desk reviewing clean color swatches on a tablet, subtle slate architectural wall in soft focus behind them, warm natural window key light balanced with cool ambient fill, shot on 35mm prime lens at f/2.0, candid natural expressions, clean upper twenty percent headroom for badge overlay, no readable screen text, no logos.

### Archetype C — `9:16` Vertical Event / Story Promo
> Vertical 9:16 studio visual centered in the middle fifty percent of the frame, luminous sculptural glass ribbon in sky-cyan and soft indigo floating effortlessly above a minimal dark slate plinth, clean uncluttered top fifteen percent and bottom twenty-five percent negative space for mobile story UI overlays, soft volumetric studio lighting, 50mm lens, crisp detail, no text or watermarks.
