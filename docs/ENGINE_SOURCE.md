# Integrated Member 1 source

The Member 2 branch integrates the committed research engine from `feature/simulation-optimization` at revision `b5712c2d5af49d70627225ae9f1a5127fb84976a`.

The `simulator`, `optimization`, `baselines`, `flexproof`, `evaluation`, `contracts`, and `configs` trees were copied unchanged from that revision. Member 1's test modules were added alongside the Member 2 API tests. The source and target were compared before copying; Member 2 had no independent edits to these research paths. No branch merge, reset, force-push, or Member 1 branch modification was performed.

The stable integration boundary is `flexproof.engine.load_scenario`, `evaluate_commitment`, and `run_scenario`. API adapters and operational verification live under `backend`; Member 2 UI code lives under `frontend`. Subsequent integration changes should keep the research engine independently importable.

Calibration outputs must be labeled calibration. Raw closed-loop held-out artifacts are not supplied by this snapshot; documented aggregate results alone cannot be treated as independently reproduced evidence.
