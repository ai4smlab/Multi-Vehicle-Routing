# Development

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD/backend:$PYTHONPATH
```

Optional env:
- `OPENROUTESERVICE_API_KEY` for the ORS adapter.

## Run
```bash
uvicorn main:app --reload
```

## Debugging (VS Code)
`.vscode/launch.json` example:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI (uvicorn)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "env": {"PYTHONPATH": "${workspaceFolder}/backend"},
      "jinja": true,
      "justMyCode": true
    },
    {
      "name": "pytest (selected)",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-k", "solomon_instance_vs_solution", "-q"],
      "env": {"PYTHONPATH": "${workspaceFolder}/backend"},
      "justMyCode": true
    }
  ]
}
```

Tips:
- Use **justMyCode** to step through your routes/solvers.
- Set breakpoints in `api/solver_routes.py` around normalization and solver dispatch.