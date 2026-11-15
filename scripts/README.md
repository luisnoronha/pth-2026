# scripts

| Script | What |
|---|---|
| `local_demo.py` | serves the Acme pages (`frontend/demo_pages/`, port 8000) and a stand-in for the attacker's webhook (port 8001) that prints `REX JUST LEAKED` when a secret arrives. Standard library only: `python scripts/local_demo.py` |
| `build_lambda.py` | builds `build/lambda.zip` for the three AWS Lambdas (Linux wheels, the `leash` package, the handlers). Run before `terraform apply`: `uv run --project strands python scripts/build_lambda.py` |
