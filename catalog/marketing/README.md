# Prism — Gemini Enterprise Low-Code Marketing Asset Pack

> **Curated 3-Item Creative Studio Pack (`2 Low-Code Agents + 1 Shared Skill`)**
> Enables marketing teams on **Google Gemini Enterprise** to produce brand-governed multi-format static visuals (**Imagen**) and short-form promotional videos (**Veo**) grounded directly in federated enterprise briefs (**Google Drive**, **Atlassian Confluence**, and **Slack**).

---

## 1. Catalog Inventory (Strict `3-Item` Ceiling)

| # | Type | Identifier | Primary Capability | Source Path |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Shared Skill (`SKILL.md` `.zip`)** | `brand-kit-governance` | Federated brief grounding (`Drive` / `Confluence` / `Slack`) + fallback Brand Kit, Imagen aspect-ratio rules, and Veo cinematography guardrails. | [`skills/brand-kit-governance/SKILL.md`](skills/brand-kit-governance/SKILL.md) |
| **2** | **Low-Code Agent (`Agent Designer`)** | `visual-copy-campaign-agent` | **Imagen** visual generation across `1:1` social, `16:9` web hero, and `9:16` vertical formats paired with channel copy, CTAs, and `alt-text`. | [`agents/visual-copy-campaign-agent/AGENT.md`](agents/visual-copy-campaign-agent/AGENT.md) |
| **3** | **Low-Code Agent (`Agent Designer`)** | `video-social-motion-agent` | **Veo** short-form video production (`text_to_video`, `image_to_video`, `first_to_last_frame`), 3-beat storyboards, camera/lighting direction, and timed supers. | [`agents/video-social-motion-agent/AGENT.md`](agents/video-social-motion-agent/AGENT.md) |

---

## 2. Prerequisites in Gemini Enterprise

1. **Provisioned Gemini Enterprise Tenant:** Stage 3 & Stage 4 completed via Prism ([`RUNBOOK.md`](../../RUNBOOK.md)), with an active Search App & Governed Assistant (`default_assistant`).
2. **Media Generation Enabled:** Ensure **Image Generation (Imagen)** and **Video Generation (Veo)** tools are enabled for your marketing user group in **Gemini Enterprise > Admin Settings**.
3. **Federated Connectors (Recommended):** Active federated **Google Drive**, **Atlassian Confluence**, and/or **Slack** collections so both agents automatically ground visuals and copy in live campaign briefs (falling back cleanly to [`brand_guidelines.template.md`](skills/brand-kit-governance/references/brand_guidelines.template.md) when no brief matches).

---

## 3. Automated API Deployment or Manual UI Import (`< 10 Minutes`)

### Option A — Automated One-Shot Deployment (`Discovery Engine v1alpha`)

Validate the catalog, build `dist/marketing/brand-kit-governance.zip`, auto-discover active federated connectors (`Google Drive`, `Confluence`, `Slack`), upload & publish the shared skill, and deploy both low-code workflow agents with `ALL_USERS` visibility:

```bash
make deploy-marketing ARGS="--project example-customer-prod --dry-run"
make deploy-marketing ARGS="--project example-customer-prod --sharing-scope ALL_USERS"
```

### Option B — Manual UI Build & Import

#### Step 1 — Customize Brand Defaults (Optional) & Build the Skill Package

If you want to tailor default brand colors, lighting descriptors, or tone pillars before uploading, edit [`skills/brand-kit-governance/references/brand_guidelines.template.md`](skills/brand-kit-governance/references/brand_guidelines.template.md), then run from the repository root:

```bash
make check-marketing     # Validate <= 3 item cap, SKILL.md frontmatter & Agent Designer schemas
make package-marketing   # Emit dist/marketing/brand-kit-governance.zip + marketing_pack_manifest.json
```

#### Step 2 — Upload the Shared Skill (`1 of 3`)

1. Sign in to the **Gemini Enterprise** web app.
2. In the left navigation bar, select **Skills** and click **+ Add** (Upload skill package).
3. Upload `dist/marketing/brand-kit-governance.zip` (structured with `brand-kit-governance/SKILL.md` at the ZIP root).
4. Share the skill with your marketing Workspace group (e.g. `{customer}-{env}-users@{domain}`).

#### Step 3 — Configure the Two Low-Code Agents in Agent Designer (`2 & 3 of 3`)

1. Open **Gemini Enterprise > Agent Designer > + New Agent**.
2. Create **`Visual & Copy Campaign Agent`** following [`agents/visual-copy-campaign-agent/AGENT.md`](agents/visual-copy-campaign-agent/AGENT.md):
   - Attach skill: `brand-kit-governance`
   - Enable tools: **Image Generation (Imagen)** and **Enterprise Search** (`Google Drive`, `Confluence`, `Slack`)
   - Paste the **System Instructions** and add the 4 starter prompt cards from [`agent_blueprint.json`](agents/visual-copy-campaign-agent/agent_blueprint.json).
3. Create **`Video & Social Motion Agent`** following [`agents/video-social-motion-agent/AGENT.md`](agents/video-social-motion-agent/AGENT.md):
   - Attach skill: `brand-kit-governance`
   - Enable tools: **Video Generation (Veo)**, **Image Generation (Imagen)** *(for start/end keyframe synthesis)*, and **Enterprise Search** (`Google Drive`, `Confluence`, `Slack`)
   - Paste the **System Instructions** and add the 4 starter prompt cards from [`agent_blueprint.json`](agents/video-social-motion-agent/agent_blueprint.json).

---

## 4. End-to-End Smoke Test Workflow

1. **Static Campaign Pack (`Visual & Copy Campaign Agent`):**
   - Click the **"Multi-Format Launch Pack (1:1, 16:9, 9:16)"** starter card.
   - Confirm the agent cites either a live Drive/Confluence brief or the fallback Brand Kit, renders crisp `1:1`, `16:9`, and `9:16` **Imagen** assets with clean typography safe zones, and outputs headlines, CTAs, `alt-text`, plus a motion handoff summary.
2. **Motion Promo Clip (`Video & Social Motion Agent`):**
   - Pass the approved hero frame (or run the **"Animate Hero Still (Image-to-Video)"** starter card) in the **Video & Social Motion Agent**.
   - Confirm the agent outputs a compact storyboard table, invokes **Veo** with a single cohesive camera move, and delivers timed supers, closed-caption script, and social post copy.
