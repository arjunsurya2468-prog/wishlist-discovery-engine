"""Embedding layer — P2 (architecture §7.2).

Owns: OpenRouter /embeddings calls + the embedding cache.
Must: cache by sha256(scrubbed_text + model_id); run the primary-vs-challenger
  bake-off once and record the choice; treat re-clustering as embedding-free.
Must NOT: re-embed on re-cluster; downgrade the model to save money; use an
  English-centric model given the Hinglish requirement (§7.1).
"""
