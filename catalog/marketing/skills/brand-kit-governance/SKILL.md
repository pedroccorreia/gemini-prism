---
name: brand-kit-governance
description: Enforces corporate brand voice, visual color palette, aspect-ratio composition rules, and media safety guardrails when producing marketing copy, Imagen static visuals, or Veo short-form video assets. Grounds dynamically in federated Google Drive, Atlassian Confluence, and Slack briefs with automatic fallback to bundled brand guidelines.
---

# Brand Kit & Creative Governance Skill

Use this skill whenever generating, critiquing, or refining **marketing visuals (Imagen)**, **short-form promotional videos or storyboards (Veo)**, or **paired campaign copy**.

## 1. Federated Brand & Campaign Grounding Protocol (Mandatory Step 1)

Before synthesizing any visual prompt, video storyboard, or campaign copy:

1. **Query Live Federated Enterprise Sources First:**
   - Search connected **Google Drive**, **Atlassian Confluence**, and **Slack** collections for:
     - Active brand books, visual style guides, or campaign creative briefs matching the user's product/launch topic.
     - Approved product positioning, taglines, target persona notes, or reference imagery/seed frames.
2. **Apply Bundled Fallback Template When Needed:**
   - If federated search returns no campaign-specific visual palette, tone rule, or brand guide (or when connectors are not yet populated), read and apply [brand_guidelines.template.md](references/brand_guidelines.template.md).
   - Explicitly tell the user whether grounding came from a **live federated brief** (citing document/page title) or the **bundled Brand Kit fallback profile**.

## 2. Progressive Modality Reference Loading

Load only the reference file matching the requested asset modality to keep context focused:

- **Static Visuals, Social Graphics, Hero Banners & Product Mockups (Imagen):**
  - Read [imagen_prompt_matrix.md](references/imagen_prompt_matrix.md) to enforce aspect-ratio framing (`1:1`, `16:9`, `9:16`), focal length, brand lighting descriptors, and post-production text safe zones.
- **Short-Form Video, Motion Promos & Storyboard Clips (Veo):**
  - Read [veo_cinematography_guide.md](references/veo_cinematography_guide.md) to structure **Text-to-Video**, **Image-to-Video**, and **First-to-Last Frame** interpolation prompts with explicit camera movement, lighting continuity, and pacing.

## 3. Non-Negotiable Brand & Media Guardrails

1. **No Garbled Baked-In Typography:** Unless the user explicitly requests rendered display typography, instruct Imagen and Veo to keep designated safe zones clean for crisp vector logo and headline overlays, and supply the exact overlay copy separately in Markdown.
2. **Color & Lighting Translation:** Translate brand hex codes into concrete physical material and lighting descriptors (for example, *"deep obsidian slate studio backdrop with subtle sky-cyan rim lighting"*) rather than raw hex strings alone, which generative media models may misinterpret or render as literal text.
3. **Trademark & Likeness Safety:** Never reference unauthorized third-party logos, copyrighted characters, celebrity likenesses, or competitor trade dress in Imagen or Veo prompts.
4. **Substantiated Claims Only:** Do not invent customer statistics, benchmark multipliers, pricing discounts, or regulatory certifications not verified in the federated campaign brief.
5. **Accessibility & Channel Readiness:** Every final visual or video deliverable must include concise accessibility `alt-text` (or closed-caption/voiceover transcript for video) alongside channel-formatted copy and a clear Call to Action (CTA).
