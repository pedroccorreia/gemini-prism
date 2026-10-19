---
description: Run staged Prism Gemini Enterprise deployment via status.py and RUNBOOK.md
---

# Deploy Prism (Gemini Enterprise)

1. Run `make status --json` to detect the live deployment phase and identify blockers.
2. Consult [AGENTS.md](AGENTS.md) for rules of engagement and [RUNBOOK.md](RUNBOOK.md) for the active stage.
3. If `owner` is `agent`: execute the recommended `next_action` (e.g. `make plan-foundation && make apply-foundation`).
4. If `owner` is `human`: halt and present the specified `handoff_template` to the human operator.
5. Repeat `make status --json` until all stages complete and `make verify` passes.
