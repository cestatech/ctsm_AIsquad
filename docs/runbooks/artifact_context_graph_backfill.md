# Artifact Context Graph Backfill

Run this after deploying artifact Context Graph registration to index artifacts
created before the fix.

From `backend/`:

```bash
python scripts/backfill_artifact_context_graph.py --dry-run
python scripts/backfill_artifact_context_graph.py
```

The command is safe to rerun. Context Graph node and edge registration is
idempotent. It registers each active artifact, its current version, the owning
study, and their `PART_OF` relationships.
