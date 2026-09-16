"""Read-only evaluation ledger lookup; never use reserved quota as actual usage."""

import re

DATABASE = re.compile(r"radar_test_[0-9a-f]{32}\Z")
OWNER = re.compile(r"[0-9a-f]{64}\Z")


def summarize(rows):
    for row in rows:
        if type(row["attempt"]) is not int or row["attempt"] < 1:
            raise ValueError("invalid ledger attempt")
        for field in ("prompt_tokens", "completion_tokens"):
            value = row[field]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("invalid ledger usage")
    unsettled = any(
        row["status"] == "pending" or row["finished_at"] is None for row in rows
    )
    metrics = {"model_calls": None if unsettled else len(rows)}
    known = {}
    for field, name in (
        ("prompt_tokens", "input_tokens"),
        ("completion_tokens", "output_tokens"),
    ):
        values = [row[field] for row in rows]
        known[name] = sum(value for value in values if value is not None)
        metrics[name] = None if unsettled or None in values else sum(values)
    return {
        "status": "unsettled" if unsettled else "settled",
        "metrics": metrics,
        "known_partial_tokens": known,
        "recorded_retry_attempts": sum(row["attempt"] - 1 for row in rows),
        "ledger": [
            {
                "id": str(row["id"]),
                "status": row["status"],
                "attempt": row["attempt"],
                "provider": row["provider"],
                "model": row["model_id"],
                "input_tokens": row["prompt_tokens"],
                "output_tokens": row["completion_tokens"],
            }
            for row in rows
        ],
        "call_count_basis": "settled ledger attempts, not a claim of successful provider billing",
    }


async def read_usage(
    connection, database, owner, client_request_id, *, variant, rejected=False
):
    if (
        not DATABASE.fullmatch(database)
        or not OWNER.fullmatch(owner)
        or not isinstance(client_request_id, str)
        or not 1 <= len(client_request_id) <= 128
        or variant not in {"legacy", "agent"}
    ):
        raise ValueError("explicit isolated evaluation identity required")
    async with connection.transaction(isolation="repeatable_read", readonly=True):
        if await connection.fetchval("SELECT current_database()") != database:
            raise ValueError("unexpected evaluation database")
        parent = await connection.fetchrow(
            "SELECT id,status,settled_at FROM public_ask_requests "
            "WHERE owner_hash=$1 AND client_request_id=$2",
            owner,
            client_request_id,
        )
        if parent is None:
            if rejected:
                return {**summarize([]), "status": "not_admitted"}
            return {
                "status": "missing",
                "metrics": {
                    "model_calls": None,
                    "input_tokens": None,
                    "output_tokens": None,
                },
            }
        fields = "c.id,c.status,c.attempt,c.provider,c.model_id,c.prompt_tokens,c.completion_tokens,c.finished_at"
        if variant == "agent":
            rows = await connection.fetch(
                f"SELECT {fields} FROM llm_calls c JOIN research_model_calls r "
                "ON r.model_call_id=c.id WHERE r.run_id=$1 ORDER BY r.sequence",
                parent["id"],
            )
        else:
            rows = await connection.fetch(
                f"SELECT {fields} FROM llm_calls c WHERE c.logical_request_id=$1 "
                "AND c.purpose='answer_generation' ORDER BY c.attempt",
                f"answer:pub-{parent['id'].hex}",
            )
        result = summarize(rows)
        if parent["status"] == "reserved" or parent["settled_at"] is None:
            result["status"] = "unsettled"
            result["metrics"] = {key: None for key in result["metrics"]}
        result["run_id"] = str(parent["id"])
        return result
