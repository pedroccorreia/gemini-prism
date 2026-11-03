# Veo Short-Form Video & Cinematography Guide

Use this guide when directing short-form promotional clips, social motion ads, and product reveals with the Gemini Enterprise **Veo** video generation tool.

---

## 1. Veo Production Modes & When to Use Each

| Veo Mode | Best Marketing Use Case | Input Requirements | Continuity Tip |
| :--- | :--- | :--- | :--- |
| **`text_to_video`** | Net-new b-roll, conceptual launch teasers, lifestyle customer vignettes, social hooks. | Structured 6-part cinematic text prompt + target aspect ratio (`16:9` landscape or `9:16` vertical). | Restrict each clip to **one continuous camera move** and **one primary action** (`4–8s` beat) to prevent motion warping. |
| **`image_to_video`** | Animating an approved **Imagen** hero graphic or **Google Drive** product photo into a living motion ad. | Approved seed image + motion prompt describing *only* how the subject, light, and camera move from that starting frame. | Do not re-describe conflicting background colors; focus on subtle physical motion (parallax dolly, light sweep, fabric/water motion). |
| **`first_to_last_frame`** | Seamless product transformations, before-and-after workflow reveals, or loopable social transitions. | Opening keyframe (`Frame A`) + Closing keyframe (`Frame B`) + interpolation prompt describing the transition path and camera arc. | Keep lens focal length and lighting color temperature consistent between `Frame A` and `Frame B` for smooth optical flow. |

---

## 2. 6-Part Veo Prompt Formula

Construct every Veo generation prompt with these six elements:

1. **Shot Type & Framing:** Wide establishing shot, medium close-up, macro tabletop shot, or vertical `9:16` mobile framing.
2. **Subject & Primary Action:** Single clear physical movement (e.g., *"a beam of white light enters a cut glass prism and fans out into cyan and teal rays"*).
3. **Camera Movement:** Choose **one** deliberate move:
   - *Slow push-in dolly* (builds focus and momentum)
   - *Smooth lateral truck / parallax slide* (adds three-dimensional depth)
   - *Subtle crane tilt-up* (signals elevation and launch reveal)
   - *Locked-off tripod with internal light/subject motion* (ideal for clean UI/copy supers)
4. **Environment & Surface Texture:** Grounded in brand materials (matte slate, warm architectural wood, sunlit glass studio).
5. **Lighting & Atmosphere:** Consistent lighting direction and mood (e.g., *soft volumetric rim light, golden-hour window light, subtle specular reflections*).
6. **Pacing & Guardrails:** Smooth real-time `24fps` cinematic motion (or `60fps` slow-motion macro); *no abrupt jump cuts, no morphing hands, no garbled on-screen text*.

---

## 3. Storyboard-First Workflow

Before invoking Veo for multi-beat campaigns, always present a compact storyboard table so the marketer can approve or tweak pacing before rendering clips:

| Scene | Beat (`s`) | Mode | Visual & Camera Direction (Veo Prompt Core) | On-Screen Super / Voiceover |
| :---: | :---: | :--- | :--- | :--- |
| **01** | `0–4s` | `text_to_video` | Medium shot, busy desk clutter smoothly clearing into a single luminous tablet, slow push-in dolly, warm natural daylight. | *"Fragmented tools slow launches down."* |
| **02** | `4–8s` | `image_to_video` | Animate approved hero product frame with a gentle parallax camera glide and subtle sky-cyan light refraction across matte slate. | *"Meet unified creative velocity."* |
| **03** | `8–12s` | `first_to_last_frame` | Smooth camera pull-back from macro glass detail (`Frame A`) to clean minimalist end-card space (`Frame B`) ready for logo lockup. | *"Start your pilot today."* |
