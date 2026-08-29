"""Interpretive layer — HUMAN-owned, post-hoc — P3 (architecture §7.6).

Owns: loading the human-authored theme->gate mapping + rationale, and deriving
  the category recommendation card.
Must: treat funnel mapping as a documented, human-owned, post-clustering layer
  with an explicit "Other — unrelated" bucket; require a one-line rationale per
  mapping; produce the recommendation as an OUTPUT of ranked+mapped themes.
Must NOT: pre-select a target category upstream; feed mapping back into clustering
  or prompts; auto-generate the mapping rationale with an LLM.
"""
