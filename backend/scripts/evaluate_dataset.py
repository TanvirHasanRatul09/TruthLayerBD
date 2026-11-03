"""Report synthetic held-out claim-match metrics; no real-world accuracy claim."""
import json
from pathlib import Path

from app.services.dataset_service import similarity


fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "dataset_eval.jsonl"
counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
for line in fixture.read_text(encoding="utf-8").splitlines():
    case = json.loads(line)
    predicted = similarity(case["query"], case["record"]) >= 0.78
    actual = case["same_claim"]
    counts["tp" if predicted and actual else "fp" if predicted else "fn" if actual else "tn"] += 1
precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0
recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0
print(json.dumps({"confusion_matrix": counts, "precision": precision, "recall": recall}, indent=2))
