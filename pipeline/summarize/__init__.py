"""LLM naming & summarization + quote validation — P3 (architecture §7.4, §7.5).

Owns: the pinned Sonnet call, prompt construction, degraded fallback, the quote
  validator (hallucination kill-switch).
Must: one call per top cluster (never per review); strict-JSON output; untrusted-
  data fenced framing; log which model produced each theme; substring-validate
  every quote before it can appear anywhere.
Must NOT (central design rule §5): put ANY hypothesis-derived language in a prompt
  — no "funnel", "consideration", "awareness", "brand schema", "category-trust".
  The banned-terms audit (P3) enforces this and must stay green.
"""
