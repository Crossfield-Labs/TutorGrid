# RAG Evaluation and Ingest Benchmark

This guide describes two local developer scripts:

- `backend/dev/evaluate_rag.py`: run offline RAG evaluation with metrics (`Recall@K`, `MRR`, latency).
- `backend/dev/benchmark_ingest.py`: benchmark multi-file knowledge ingestion throughput.

## 1) RAG Evaluation Dataset Format

Save a json file like:

```json
{
  "courseName": "Software Architecture",
  "courseDescription": "RAG benchmark set",
  "documents": [
    {
      "path": "../data/samples/observer.md",
      "name": "observer-notes",
      "chunkSize": 900
    },
    "../data/samples/strategy.md"
  ],
  "queries": [
    {
      "question": "What is the core idea of observer pattern?",
      "expectedPhrases": ["one-to-many", "publish-subscribe"],
      "limit": 8,
      "id": "q-observer-1"
    },
    {
      "question": "When should strategy pattern be used?",
      "expectedPhrases": ["encapsulate algorithms"],
      "limit": 8
    }
  ]
}
```

Notes:
- `documents` supports string path or object.
- relative paths are resolved against the dataset file directory.
- metrics are computed only for queries with non-empty `expectedPhrases`.

## 2) Run RAG Evaluation

```powershell
.venv\Scripts\python.exe -m backend.dev.evaluate_rag `
  --dataset docs/examples/rag_eval_dataset.json `
  --db-path scratch/eval-rag/orchestrator.sqlite3 `
  --kb-root scratch/eval-rag/knowledge_bases `
  --ks 1,3,5,10 `
  --output scratch/eval-rag/report.json
```

Useful options:
- `--reuse-course-id <course_id>`: skip ingestion and evaluate an existing course.
- `--max-queries <n>`: evaluate only first `n` queries.
- `--default-limit <k>`: fallback retrieval limit for queries without `limit`.

## 3) Run Ingest Benchmark

Using explicit files:

```powershell
.venv\Scripts\python.exe -m backend.dev.benchmark_ingest `
  data/samples/observer.md data/samples/strategy.md `
  --chunk-size 900 `
  --output scratch/ingest-benchmark/report.json
```

Using a manifest file:

```powershell
.venv\Scripts\python.exe -m backend.dev.benchmark_ingest `
  --manifest docs/examples/rag_eval_dataset.json `
  --output scratch/ingest-benchmark/report.json
```

The benchmark output includes:
- success/failed file counts
- total chunks
- total/avg duration
- files per minute
- chunks per second

## 4) Compare RAG Profiles

Run a profile sweep on the same dataset and same ingested course:

```powershell
.venv\Scripts\python.exe -m backend.dev.compare_rag_profiles `
  --dataset docs/examples/rag_eval_dataset.json `
  --db-path scratch/eval-rag/compare/orchestrator.sqlite3 `
  --kb-root scratch/eval-rag/compare/knowledge_bases `
  --ks 1,3,5 `
  --output-json scratch/eval-rag/compare/profile_compare.json `
  --output-md scratch/eval-rag/compare/profile_compare.md
```

Default profile set:
- `baseline`: multi-query off, HyDE off, rerank off
- `mq_hyde`: multi-query on, HyDE on, rerank off
- `full_rag`: multi-query on, HyDE on, rerank on

You can provide custom profiles:

```json
{
  "profiles": [
    {
      "name": "custom-a",
      "description": "example",
      "env": {
        "ORCHESTRATOR_RAG_MULTI_QUERY": "1",
        "ORCHESTRATOR_RAG_HYDE": "0",
        "ORCHESTRATOR_RAG_RERANK": "1"
      }
    }
  ]
}
```

Then run with:

```powershell
.venv\Scripts\python.exe -m backend.dev.compare_rag_profiles `
  --dataset docs/examples/rag_eval_dataset.json `
  --profiles docs/examples/rag_profiles.json
```

## 5) Grid Tuning (Chunk Size x Profile)

Run full grid tuning and generate recommendation:

```powershell
.venv\Scripts\python.exe -m backend.dev.tune_rag_grid `
  --dataset docs/examples/rag_eval_dataset.json `
  --chunk-sizes 600,900,1200 `
  --profiles docs/examples/rag_profiles.json `
  --output-json scratch/eval-rag/grid/tune_report.json `
  --output-md scratch/eval-rag/grid/tune_report.md
```

Output includes:
- per-variant metrics and weighted score
- best variant recommendation
- markdown top-N ranking table

## 6) Generate Recommendation Brief

After running both profile compare and grid tuning, generate a concise recommendation report:

```powershell
.venv\Scripts\python.exe -m backend.dev.summarize_rag_reports `
  --profile-report scratch/eval-rag/compare/profile_compare.json `
  --grid-report scratch/eval-rag/grid/tune_report.json `
  --output-json scratch/eval-rag/recommendation.json `
  --output-md scratch/eval-rag/recommendation.md
```

The summary report contains:
- recommended default config (`chunk size + profile`)
- delta against baseline
- top variant table for fast review

## 7) Validate Real Dataset Before Running

Validate format and file paths:

```powershell
.venv\Scripts\python.exe -m backend.dev.validate_rag_dataset `
  --dataset docs/examples/real_rag_dataset_template.json
```

Use strict mode for readiness checks:

```powershell
.venv\Scripts\python.exe -m backend.dev.validate_rag_dataset `
  --dataset path/to/your_real_dataset.json `
  --strict
```

Templates:
- `docs/examples/real_rag_dataset_template.json`
- `docs/examples/real_rag_questions_template.csv`

## 7.1) Build Dataset JSON From CSV

If your team prepares questions in CSV, generate dataset json automatically:

```powershell
.venv\Scripts\python.exe -m backend.dev.build_rag_dataset `
  --course-name "Software Architecture" `
  --course-description "2026 spring course set" `
  --questions-csv docs/examples/real_rag_questions_template.csv `
  --doc-paths path/to/week01.pptx path/to/week01.docx path/to/patterns.pdf `
  --chunk-size 900 `
  --output scratch/eval-rag/real_dataset.json
```

You can also provide `--doc-manifest` with a json/list file.

## 8) One-Command End-to-End Workflow

Run validation, profile compare, grid tuning, and recommendation in one command:

```powershell
.venv\Scripts\python.exe -m backend.dev.run_rag_workflow `
  --dataset path/to/your_real_dataset.json `
  --profiles docs/examples/rag_profiles.json `
  --chunk-sizes 600,900,1200 `
  --strict-validate `
  --run-root scratch/eval-rag/workflow
```

Output directory contains:
- `run_manifest.json`
- `profile_compare.json` / `.md`
- `tune_report.json` / `.md`
- `recommendation.json` / `.md`
