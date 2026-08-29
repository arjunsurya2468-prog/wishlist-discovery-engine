"""Publish layer — P4 (architecture §7.7).

Owns: Airtable upserts (5 tables, §9) and analysis.json generation.
Must: keep the Airtable token server-side (env only); surface a PUBLIC read-only
  share link; keep review-mined vs primary-research counts in separate
  tables/fields (never summed); write a RunLog row per run.
Must NOT: embed the token in client code/repo/artifact; blend Triangulation
  numbers into review-mined numbers; write human-owned fields from code.
"""
