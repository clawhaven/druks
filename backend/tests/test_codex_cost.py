import json
from pathlib import Path

from druks.harnesses.codex import read_codex_cost_from_jsonl


def test_read_from_jsonl_handles_event_msg_payload_wrapper(tmp_path: Path) -> None:
    """Regression: newer codex builds wrap token_count events as
    ``{"type":"event_msg","payload":{"type":"token_count","info":{...}}}``.
    The parser must read ``info`` from the nested payload, not the
    top-level event."""
    path = tmp_path / "codex-session.jsonl"
    event = {
        "timestamp": "2026-06-07T14:41:03.746Z",
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "model": "gpt-5.5",
                "total_token_usage": {
                    "input_tokens": 42045,
                    "cached_input_tokens": 2432,
                    "output_tokens": 738,
                    "reasoning_output_tokens": 263,
                    "total_tokens": 42783,
                },
            },
        },
    }
    path.write_text(json.dumps(event) + "\n")

    cost, metadata = read_codex_cost_from_jsonl(path, model="gpt-5.5")

    assert cost is not None and cost > 0
    assert metadata is not None
    assert metadata["input_tokens"] == 42045
    assert metadata["output_tokens"] == 738
    assert metadata["reasoning_output_tokens"] == 263
