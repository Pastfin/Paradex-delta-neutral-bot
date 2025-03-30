import json
from pathlib import Path
from typing import Any, Dict

from src.config.paths import CONFIG_PATH, STATE_PATH


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def dump_json(path: Path, json_file: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(json_file, file, ensure_ascii=False, indent=2)


def update_state(private_key: str, key: Any, value: Any) -> None:
    path = Path(STATE_PATH)
    state = load_json(path)

    if private_key not in state:
        state[private_key] = {}

    state[private_key][str(key)] = value
    dump_json(path, state)


def get_user_state() -> Dict[str, Any]:
    return load_json(Path(STATE_PATH))


USER_CONFIG: Dict[str, Any] = load_json(Path(CONFIG_PATH))
