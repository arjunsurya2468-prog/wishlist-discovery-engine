"""App backend — P5 (architecture §7.8).

Owns: static serving, POST /api/live-run, GET /healthz, rate limiting.
Must: reuse pipeline normalize/embed code; assign to the LOCKED taxonomy only;
  keep all keys server-side; rate-limit + cool down; degrade gracefully.
Must NOT: re-cluster live; require visitor login/keys; expose any secret to the
  client; let a live-run failure prevent the static render.
"""
