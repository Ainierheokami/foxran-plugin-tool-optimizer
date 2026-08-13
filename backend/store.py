from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from app.runtime.paths import DATA_DIR

from .schemas import OptimizationRule


class RuleStore:
    def __init__(self, root: Path | None = None) -> None:
        configured_root = os.environ.get("FOXRAN_TOOL_OPTIMIZER_DATA_DIR")
        self.root = root or (
            Path(configured_root).expanduser().resolve()
            if configured_root
            else DATA_DIR / "extensions" / "tool_optimizer"
        )
        self.rules_path = self.root / "rules.json"
        self._lock = threading.RLock()

    def ensure_storage(self) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            if not self.rules_path.exists():
                self._write([])

    def _write(self, rules: list[OptimizationRule]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.rules_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                [rule.model_dump(mode="json") for rule in rules],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.rules_path)

    def list_rules(self) -> list[OptimizationRule]:
        with self._lock:
            self.ensure_storage()
            payload = json.loads(self.rules_path.read_text(encoding="utf-8") or "[]")
            rules = [OptimizationRule.model_validate(item) for item in payload]
            return sorted(rules, key=lambda item: (item.priority, item.id))

    def save_rule(self, rule: OptimizationRule) -> OptimizationRule:
        with self._lock:
            rules = self.list_rules()
            by_id = {item.id: item for item in rules}
            by_id[rule.id] = rule
            self._write(sorted(by_id.values(), key=lambda item: (item.priority, item.id)))
            return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            rules = self.list_rules()
            kept = [rule for rule in rules if rule.id != rule_id]
            if len(kept) == len(rules):
                return False
            self._write(kept)
            return True
