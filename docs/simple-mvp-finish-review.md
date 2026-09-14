disposition: fix

Review scope: existing-world, code-first comparison MVP; no new comp, quality card, raster assets, or concept seed is required by the supplied surface brief. All eight required round-2 captures were visually inspected. Optional original-page captures were not reopened; original-route regression evidence was read separately. Global CSS was sampled, not exhaustively audited.

## persistence

Pass. PRODUCT.md exists and preserves the synthetic-data and source-evidence constraints. DESIGN.md records the incumbent silver-blue reading world; the preview-specific layout and interaction changes are persisted in .impeccable/surfaces/frontend-src-preview-previewhome-vue.md. App.vue and main.ts expose /preview and /preview/ask while retaining the four original routes. No comp-led build state is applicable to this refinement.

Evidence passes: desktop and mobile home, full home, reader, and ask captures are present, nonblank, correctly framed, and show the named states. The full-page images begin at the document top. Supplied capture geometry passes 8/8. Read verification reports show 27/27 preview behavior checks, 42/42 original-page checks dated 2026-09-14T01:09:01Z, and 18/18 unit checks plus type checking and production build. These are separate checks, not a combined product acceptance rate. The detector report is empty; no second detector ran.

## fidelity

| Element / promise | Verdict | Evidence |
| --- | --- | --- |
| TYPE | match | Natural Chinese working typography, restrained event titles, stronger reader title, and blue date numerals retain OWN-WORLD and the explicitly incumbent typography in DESIGN.md. The request does not introduce a new display identity. |
| MATERIAL | match | White reading planes, soft offset shadows, and pale quote fields retain the abstract cloud-plane treatment. There is no imitation physical material or missing raster obligation. |
| GROUND | match | Both viewport sets keep the cool silver-blue page field; preview.css declares the authorized #edf2f7 ground. Reader content remains white. |
| THESIS: event and evidence in one opening | match | Both reader captures show event context and the saved quotation together, without another evidence-opening action. |
| OWN-WORLD: compact date rhythm | contradicted | Daily dates float toward the middle of the row while their disclosure chevrons remain at the far left. On desktop the date sits hundreds of pixels from its chevron; the same separation persists on mobile. The date no longer reads as one compact control aligned with its event group. |
| STORY: secondary details when needed | contradicted | The collapsed 日期, 来源信息, and 研究条件（可选） controls lack a visible disclosure marker in all relevant captures. The flex summary styling suppresses the native marker, leaving the user to infer that the text expands content. |
| FIRST VIEWPORT: earlier event reading | adaptation | The supplied brief authorizes replacing the side rail and contextual statistics with a compact top bar and a single event stream. First-event geometry is 407px desktop and 535px mobile; these positions support the layout promise and are not human task-time measurements. |
| FORM: comparison preview in the existing world | match | The preview label, return-to-original link, dedicated routes, and reused Ask page implement the authorized comparison scope. The explicit existing-world FORM explains the absence of a new concept roll. |
| Reading focus and responsive reflow | adaptation | The single desktop reader becomes a full mobile reading surface, as authorized by the confirmed one-opening evidence flow. Its visible close control and reported modal, focus, Escape, and history checks support protected reading focus. |
| Truth and provenance | match | Home and reader captures label fixture content synthetic, including the source version and quotation. The empty Ask form contains no synthetic answer. Source version, paragraph, and verification fields remain in the implementation's expandable details. |

## ceiling

The established world's relevant devices are present: cool ground, continuous white reading plane, quiet blue controls, inset quote field, and restrained reader motion with reduced-motion handling. Greater ornament or a new display identity would exceed this refinement's scope. The ceiling is currently limited by disclosure discoverability and the broken daily date alignment, not by missing decorative assets.

## material_fixes

1. STORY / craft coverage: restore a consistent visible disclosure chevron beside 日期, 来源信息, and 研究条件（可选）, with an expanded-state change; preserve native details semantics and 44px targets. The collapsed controls must visibly read as expandable without requiring a trial click.
2. OWN-WORLD / FIRST VIEWPORT: keep each daily chevron and complete date together at the event group's left edge, with the loaded count separated at the right. Replace the three-way space-between distribution caused by the pseudo-element; apply the same alignment to every day group at desktop and mobile sizes.

## keep

Keep saved evidence visible on the first event opening, the continuous reading plane, explicit synthetic labels, immediate search/category filtering, optional research conditions, and the return to the original interface.
