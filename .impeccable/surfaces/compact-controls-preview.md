# Compact controls preview
Target: frontend/public/controls-preview.html
Mode: Operate / Read. Isolated interactive preview; no replacement of homepage or production controls.
User approved B lightweight toolbar, date popover, assistant history, richer rounded heatmap.
## Direction contract
THESIS: Reduce control weight while preserving discoverability; primary actions, filters and list rows have distinct roles.
OWN-WORLD: Existing silver-blue reading space; navy ink, pale blue selection, 32px desktop controls, 6px radius, compact 28px secondary actions, 44px touch targets.
STORY: Compare old and new controls, select dates, understand category-by-day counts, inspect events, and try history without a blocking resize layer.
FIRST VIEWPORT: Slim header; comparison rows above statistics; range toolbar, total and heatmap on left; assistant and foldable history on right, combined at most half desktop viewport. Mobile single pane with explicit assistant return.
FORM: Approved B local extension, code-led. Seed not applicable: precisely specified local preview. Date-only picker with presets, calendar and apply; 60 days deterministic synthetic records shared by counts and drill-down. Resize separators never inherit button padding or full-width row styles.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Completion: isolated preview implemented and reviewed; three reviewer fixes resolved (ship scoped to that list). Preview-specific design notes preserve production DESIGN.md and sidecar. No shipping raster assets.
