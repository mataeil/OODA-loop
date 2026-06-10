# Fully-isolated E2E environment for OODA-loop.
# stdlib-only Python + git — no pip installs, no network at test time.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && git config --global user.email "ooda-e2e@local" \
 && git config --global user.name "OODA E2E" \
 && git config --global init.defaultBranch main

WORKDIR /repo
COPY . /repo

# Official test process, both tiers, in one isolated container:
#   Tier 0 — static fixture walkthrough (tests/verify.py)
#   Tier 1 — Docker E2E rail scenarios (tests/e2e/scenarios)
CMD ["bash", "-c", "set -e; \
     echo '=== Tier 0: static verify ==='; python3 tests/verify.py; \
     echo '=== Tier 1: E2E rail scenarios ==='; \
     python3 -m unittest discover -s tests/e2e/scenarios -v"]
