\set ON_ERROR_STOP on
DO $check$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') THEN
    RAISE EXCEPTION 'Restored database is missing vector';
  END IF;
  IF EXISTS (
    SELECT 1 FROM evidence e LEFT JOIN article_versions v ON v.id=e.article_version_id
    WHERE v.id IS NULL OR NOT (v.paragraphs ? e.paragraph_id)
       OR strpos(coalesce(v.paragraphs ->> e.paragraph_id,''), e.quote_text)=0
  ) THEN
    RAISE EXCEPTION 'Restored Evidence no longer locates in frozen paragraphs';
  END IF;
  IF EXISTS (
    SELECT 1 FROM event_entities ee
    LEFT JOIN events e ON e.id=ee.event_id LEFT JOIN entities n ON n.id=ee.entity_id
    WHERE e.id IS NULL OR n.id IS NULL
  ) THEN
    RAISE EXCEPTION 'Restored entity relationships are incomplete';
  END IF;
END
$check$;
SELECT count(*) AS located_evidence FROM evidence;
SELECT count(DISTINCT e.id) AS deepseek_subject_events
FROM events e JOIN event_entities ee ON ee.event_id=e.id
JOIN entities n ON n.id=ee.entity_id
WHERE e.status='published' AND ee.role IN ('subject','product')
AND (lower(n.canonical_name) LIKE '%deepseek%' OR EXISTS (
  SELECT 1 FROM entity_aliases a WHERE a.entity_id=n.id AND a.normalized_alias='deepseek'
));
