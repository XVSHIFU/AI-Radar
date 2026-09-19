# Content workbench API

This contract is implemented by `backend/src/radar/content_api.py`. Routes are under
`/api/v1/admin/content`, require the existing administrator session cookie, and require
`X-CSRF-Token` for writes. The administrator Bearer token accepted by existing admin
routes also works. Responses carry `Cache-Control: no-store`; model credentials are never
returned.

## Manual flow

| Route | Request | Response |
| --- | --- | --- |
| `GET /articles?limit=50` | — | `{items:[{article_version_id,title,source_url,published_at,content_hash,task_id,status}],total}` |
| `POST /tasks` | `{article_version_ids:[uuid]}` (1–5) | `{items:[task]}` |
| `GET /tasks?limit=100` | — | `{items:[task],total}` |
| `POST /export` | `{task_ids:[uuid]}` (1–5) | `{prompt,task_ids}` |
| `POST /import` | `{text:"JSON or fenced JSON"}` | `{items:[{task_id,status,draft_id,errors}]}` |
| `GET /drafts/{id}` | — | Draft, validation errors, and frozen article paragraphs |
| `PATCH /drafts/{id}` | `{revision,content}` | Updated draft and incremented revision |
| `POST /drafts/{id}/publish` | `{revision}` | `{status,event_id,draft_id}` |
| `POST /tasks/{id}/skip` | Empty | Updated task with `status:"skipped"` |
| `POST /tasks/{id}/manual` | Empty | Detaches an unclaimed task from its auto batch |

`POST /tasks` reuses an existing task for the same frozen version. Only latest frozen
versions with a candidate in `needs_review`, `extraction_failed`,
`extraction_unknown`, or `filtered` are selectable. A task binds the server's
article version ID, content hash, prompt version, and schema version. Import accepts
one object, an array, or `{"results":[...]}`, optionally inside a JSON code fence.
Each result must contain the exported `task_id`; other article IDs, URLs, or hashes
from the generator have no authority. Errors are per item. An identical repeated
import returns the existing draft. A changed repeated import does not overwrite it;
use the draft editor with its revision.

The export is at most 48,000 UTF-8 bytes. Long frozen paragraphs are excerpted
without changing paragraph IDs; the exact exported excerpts are stored with the
task. Evidence quotes must occur verbatim in that stored scope. The server also
checks entity/category/date rules from `ExtractionResult`; a quote match does not
change evidence verification status from `unverified`. A relevant:false result
stays an editable invalid draft until the administrator explicitly skips it.
Publishing locks the task and draft, rechecks the current frozen version, and uses
the shared event/evidence/entity publisher. Repeating publish returns the same
event; manual publishing creates no `llm_calls` row.

A publishable `content` object has this shape:

```json
{
  "relevant": true,
  "title_zh": "中文标题",
  "summary_zh": "中文短摘要",
  "category": "model_release",
  "importance": 3,
  "event_date": null,
  "date_precision": "unknown",
  "date_basis": "unknown",
  "date_evidence_paragraph_id": null,
  "entities": [{"canonical_name": "Example AI", "entity_type": "company", "role": "subject"}],
  "evidence": [{"paragraph_id": "p-0001", "quote_text": "Exact source quote", "claim_key": null, "claim_text": null, "support_type": "direct"}]
}
```

The categories are `model_release`, `agent_tool`, `framework_sdk`,
`research`, `product`, and `industry`. Entity types are `company`,
`person`, `product`, `model`, `organization`, and `technology`.
Entity roles are `subject`, `product`, and `mention`. Support types are
`direct`, `context`, and `contradicts`. Known event dates need explicit
paragraph evidence in the frozen article; a reported or fetched date is not
substituted.

## Optional automatic mode

| Route | Request | Response |
| --- | --- | --- |
| `GET /settings` | — | Switches, caps, profile metadata, `profile_version` |
| `PATCH /settings` | Switches/caps and optional `profile:{provider,base_url,model,api_key}` | Updated settings without API key |
| `POST /batches` | `{task_ids:[uuid]}` | `{id,status:"queued"}` |
| `GET /batches/{id}` | — | Batch status, bound profile version, task items |
| `POST /batches/{id}/pause` | Empty | Paused batch; unclaimed items become manual |

Automatic mode defaults disabled with daily article/input/output caps all zero,
auto publish off, at most one model call per article, and concurrency one. The
profile lives in `content-model.json` next to the existing `model.json`; it
does not overwrite the public assistant profile. Saving settings makes no model
call. Updating the profile while a batch is queued or running is rejected.
A batch snapshots profile metadata and version, and only selected task IDs
are processed. The API process sends each bounded frozen prompt through the
pi content runtime's `/v1/content` route. Its one-use capability allows one
`/internal/content/model` call bound to the trusted prompt and output cap;
the pi content Agent has no tools. The backend reserves conservative input
and output tokens in `content_usage` before dispatch. Missing usage,
transport uncertainty, or a restart retains the reservation as unknown and
pauses the batch. It never automatically retries or switches providers.
Successful output enters the same draft and publisher. Auto publish applies
only when explicitly enabled.

Migration `0014_content_workbench` creates the persistent task, draft,
settings, batch, and usage tables; readiness expects this revision.

