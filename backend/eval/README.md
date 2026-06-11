# Generator model eval harness

Empirically answers: **what is the smallest / cheapest model that produces
review-ready CDISC and regulatory artifacts on our actual generator prompts?**

It runs the platform's real generators (`SDTMMappingGenerator`,
`ProtocolGenerator`, …) — their exact system prompts, user-prompt construction,
and JSON parsing — against any mix of frontier and locally-hosted models, then
scores the outputs. It never touches the database or the CIP audit chain; it
imports the generator classes only to reuse their prompts.

## Why this exists

The "~70B floor" for the CDISC data tier and "frontier-class for authoring" was
an *estimate*. This harness replaces the estimate with measurement on your own
study shapes. Two numbers decide the question:

1. **JSON validity / CDISC conformance** — automated here. Cheap, deterministic.
2. **Reviewer-correction rate** — how much a human must edit a draft to ship it.
   Inherently human; the harness emits a scoring sheet for it and gives you
   automated proxies (schema coverage, placeholder rate) to make review fast.

## What it measures (automated)

Per (model × generator × fixture):

| Metric | Meaning |
|---|---|
| `json_valid` | the real parser returned a dict |
| `first_attempt_valid` | valid without the SAP repair-retry firing |
| `schema_coverage` | fraction of documented top-level keys present & non-empty |
| `cdisc_pass_rate` | from the platform's own `run_cdisc_validation` rule engine |
| `placeholder_rate` | fraction of leaf values left as stubs ("", `null`, "<title>", "To be specified") |
| `output_tokens`, `latency_s` | cost / throughput |

The CDISC rule engine is the same deterministic oracle described in the
model-size discussion — it lets a smaller model's structural errors be *caught*,
and here it scores them.

## Setup

From `backend/`, with the venv active:

```bash
cp eval/models.example.yaml eval/models.yaml
# edit eval/models.yaml: enable your local endpoints, set base_url/model_id
export ANTHROPIC_API_KEY=sk-...   # only needed for anthropic entries
```

No new dependencies — the harness uses `anthropic`, `httpx`, and `pyyaml`,
all already vendored.

### Pointing at a local model

Any OpenAI-compatible server works. Set `base_url` to the server root including
`/v1`:

- **vLLM**: `python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-72B-Instruct` → `http://localhost:8000/v1`
- **Ollama**: `ollama serve` then `ollama pull llama3.3:70b` → `http://localhost:11434/v1`
- **LM Studio**: start its local server → `http://localhost:1234/v1`
- **TGI**: → `http://localhost:8080/v1`

## Run

```bash
# Full sweep: every enabled model × all 7 generators × all fixtures
python -m eval.harness --config eval/models.yaml --out eval/results

# Narrow it down while iterating
python -m eval.harness --config eval/models.yaml \
    --artifacts SDTM_DATASET ADAM_DATASET TLF \
    --fixtures onc-ph2-nsclc \
    --concurrency 2          # lower for a single local GPU
```

Artifact types: `SDTM_DATASET ADAM_DATASET TLF PROTOCOL SAP ICF CSR`.

## Outputs (in `--out`, default `eval/results/`)

- **`summary.md`** — per-model aggregates, plus the **CDISC-data vs authoring**
  split that answers "how small can we go, and where". Read this first.
- **`results.csv`** — one row per cell, every metric. For your own pivots.
- **`review_template.csv`** — one row per cell with blank columns
  (`fields_reviewed`, `fields_corrected`, `reviewer_correction_rate`,
  `semantic_errors`, `acceptable_as_draft`, `reviewer_notes`). **Have a
  CDISC/medical reviewer fill this in** — it's the deciding metric.
- **`raw/`** — every generated artifact as JSON (or `.invalid.txt` when the
  model produced unparseable output), referenced by the review template.

## Reading the result

- A local model with high `json_valid` + high `cdisc_pass_rate` on the **data**
  tier but a falling `schema_coverage` on the **authoring** tier is the signal
  for the routed setup: small local model for SDTM/ADaM/TLF, larger model for
  Protocol/SAP/CSR.
- Low `first_attempt_valid` but high `json_valid` means the model needs the
  repair retry a lot — workable, but add constrained/grammar JSON decoding on
  the serving side before trusting it.
- High `placeholder_rate` means the model returns scaffolding, not content — it
  will drive up the human correction rate even when JSON is valid.

## Extending

- **More representative fixtures** → edit `fixtures.py`. The closer they are to
  your real studies, the more trustworthy the reported floor.
- **Different scoring** → `scoring.py`. The CDISC oracle is `run_cdisc_validation`.
- **Another backend** → add a `ModelClient` subclass in `model_clients.py`.
