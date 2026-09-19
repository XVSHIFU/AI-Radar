> Historical extractor notes: provider restrictions and date rules below describe an earlier implementation. Paid extraction is currently paused. The current manual-first / optional content-Agent plan is [content-pipeline-plan.md](content-pipeline-plan.md); do not restart this command as part of that planning work.

# DeepSeek Flash offline event extraction

The extractor publishes structurally validated AI events from immutable `ArticleVersion` rows. It is an
operator-run batch and does not enable the public ask endpoint.

## Configuration

Set `DATABASE_URL` (or the split `DB_*` variables) and `LLM_API_KEY`. The client rejects any
base URL other than `https://api.deepseek.com`, any model other than `deepseek-flash`, and any
`LLM_MAX_TOKENS` value above 2000. Requests use JSON output and disable thinking.

Provider balance is the spending boundary. The application does not estimate prices or reserve
currency. Start with a small `--limit`; HTTP 401, 402, or an `insufficient_balance` response stops
the batch immediately.

```bash
cd backend
python -m radar.extract_events \
  --date-from 2026-08-01 \
  --date-to 2026-09-15 \
  --limit 3
```

The limit counts distinct frozen versions claimed for a provider call. Selection rotates across
sources and puts arXiv sources last so a small first batch covers several official product/news
feeds. Re-running the same command skips every version with an existing extraction call, including
unknown timeouts, so it cannot silently pay twice. Operators must inspect an unknown call before
any manual recovery.

## Publication rules

- The event date is a **source report/publication date**, not a model-generated occurrence time.
  A timestamp is converted to `Asia/Shanghai`. If the frozen timestamp is absent, the extractor
  accepts only a matching discovery's exact `YYYY-MM-DD` value and keeps day precision. Other
  unknown dates are excluded.
- A relevant result needs a Chinese title and summary, a controlled category, importance 1–5,
  and at least one evidence quote. Each quote must be an exact substring of its named paragraph in
  the frozen version. Substring validation is structural, so stored evidence remains `unverified`.
- Irrelevant content is marked `filtered`. Empty, malformed, truncated, or unlocatable evidence is
  marked `extraction_failed`. Transport timeouts are marked `extraction_unknown` and are not
  retried automatically.
- Candidates from multiple sources that point to the same version share one extraction. A newer
  version of the same article updates the event linked through `EventArticle`, increments
  `content_version`, and adds version-specific evidence without deleting older evidence.

`llm_calls` records the idempotency key, provider response ID, token usage when returned, response
content hash, terminal state, and error code. It does not record the API key or computed cost.
