# Orchestrator

This directory is the standalone rewrite of the PC orchestrator on top of LangGraph and LangChain.

Design direction:
- Rebuild the runtime inside `orchestrator/` instead of importing legacy root modules.
- Keep protocol, session management, runners, runtime, tools, workers, and providers inside this directory.
- Promote this directory to the future project root after the rewrite becomes feature-complete.

Local setup:

```powershell
python -m pip install -r orchestrator/requirements.txt
python -m compileall orchestrator
python -m orchestrator.main --host 127.0.0.1 --port 3210
```

Configuration:
- Copy `config.example.json` to `config.json` inside `orchestrator/`
- `config.json` is ignored by Git
- Environment variables still override file-based values

Current status:
- `server/` contains the new WebSocket entrypoint and protocol layer
- `sessions/` contains the new in-memory session model and manager
- `runtime/` contains the LangGraph runtime shell
- `runners/`, `tools/`, `workers/`, and `providers/` contain the new standalone execution stack
