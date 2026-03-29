import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)

    if isinstance(value, list):
        return [_to_serializable(item) for item in value]

    if isinstance(value, dict):
        return {key: _to_serializable(val) for key, val in value.items()}

    return value


def write_jsonl_log(file_path: str, record: Any) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    serializable_record = _to_serializable(record)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(serializable_record, ensure_ascii=False) + "\n")