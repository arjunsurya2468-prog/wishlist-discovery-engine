"""Clustering & ranking layer — P2 (architecture §7.3).

Owns: UMAP->HDBSCAN fit, persisted centroids (the locked taxonomy), ranking.
Must: cluster EVERYTHING (relevance flag invisible here); fix random_state=42;
  persist centroids for the live run; rank by size × share_of_relevance-flagged
  (rating-agnostic); abort below config.ML_FLOOR reviews.
Must NOT: use size × (6 − avg_rating) (buries the target signal); let the
  relevance flag influence clustering; hide any cluster.
"""
