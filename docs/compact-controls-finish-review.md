# Compact controls preview — finish review

## Persistence

Disposition: **fix**. The approved B direction is suitable for this isolated preview; a rebuild is unnecessary. This is not acceptance of the production homepage, statistics page, real news collection, or AI generation.

The surface contract is persisted in `.impeccable/surfaces/compact-controls-preview.md`; PRODUCT.md and DESIGN.md establish the existing silver-blue reading space. The preview sources are `frontend/public/controls-preview.{html,css,js}`. Keep the final preview-specific decisions in DESIGN.md without replacing production component rules.

This review opened all eight supplied captures under `.impeccable/review/compact-controls/`: `desktop.png`, `desktop-date.png`, `desktop-conversation.png`, `mobile.png`, `mobile-date.png`, `mobile-assistant.png`, `mobile-history.png`, and `tablet-date.png`. Desktop captures use a 1680×1000 viewport, mobile 390×844, and tablet 1024×768; base desktop/mobile captures include the full page. The supplied captures were recorded on 2026-09-14 around 20:27 local time.

Recorded evidence includes 18/18 interaction checks, successful conversation reload, mobile page overflow/date containment, and tablet date containment. These are useful functional evidence, but `multi_turn` and `composer_not_covered` passing do not establish a readable populated conversation: its screenshot visibly fails. Local persistence is demonstrated for this preview only.

## Fidelity

The old/new comparison communicates the requested hierarchy immediately: dark primary action, pale selected filter, and quiet contextual actions. The 32px desktop toolbar is visibly lighter than the old controls. The familiar navy ink, pale blue selection, small radii, flat event rows, and existing Inter/system Chinese stack preserve the chosen world.

The desktop, mobile, and tablet date captures show start/end dates, presets, a single calendar, cancellation, and application without time controls. The panel remains within the shown viewports. The mobile composition is usable visually but its control dimensions still miss the contract's touch target floor.

The rounded red heatmap is materially richer than a sparse placeholder. Recorded checks establish 1,029 deterministic synthetic records across 60 days, with the displayed 30-day total of 537 shared by the chart and list. Counts, zero values, category labels, and a local synthetic-data notice are present. The heatmap's measured cell contrast passes at 5.59:1. This is an event-count visualization, not evidence of real industry activity.

Assistant and history share a restrained desktop pane, with no visible history-button layer covering the welcome state. Source confirms resize edges are 6px separators with zero padding and transparent backgrounds. Mobile assistant and history each occupy a single pane. Populated conversation fidelity fails for the reason below.

## Ceiling

The author completed two screenshot rounds. This independent review used the supplied artifacts and source; it did not run another browser round or detector. Stop discretionary polish. Make the material fixes below together, then capture only the affected states to establish closure.

The detector ran once. Its recorded 10px functional-text and colored-shadow findings predate the current CSS, which uses 11px for the affected labels and neutral offset shadows. The Inter warning is accepted because preserving the established type system is an explicit direction decision. Do not rerun the detector to erase that warning or replace the font.

The target ceiling is a coherent, interactive local comparison that makes the four proposed changes reviewable. It does not require a new visual identity, production integration, AI behavior, or additional decorative assets.

## Material fixes

1. **Blocking — scope the assistant shell styles.** `desktop-conversation.png` shows an answer beginning at the pane's top edge, clipped role text, and the assistant header/history/composer obscured. In `controls-preview.js`, `renderChat()` emits `article.message.assistant`; the global `.assistant` selector in `controls-preview.css` gives that message fixed shell positioning, width, background, and stacking. Scope every shell selector, including mobile and closed-state variants, to the shell ID or a unique shell class. Keep message roles distinct. Verify a submitted conversation and a restored historical conversation: messages must remain inside the scroll region, header and composer must remain visible, and history must remain operable. Recapture populated desktop and mobile conversation states; an empty welcome screenshot cannot close this finding.

2. **Required — honor the 44px mobile touch target contract.** At the mobile breakpoint, `.calendar-day` is 36px high and `.heat-cell` is 32px high; date fields retain a 30px minimum. Calendar column widths are also below 44px in the shown preset-plus-calendar layout. Make mobile date fields and calendar targets at least 44×44px. A compact horizontal/wrapping preset group above the mobile calendar can preserve the date-only structure while allowing seven 44px columns. Increase mobile heatmap targets to 44×44px within its existing horizontal scroller, retaining sticky categories and readable dates. Desktop density can stay unchanged. Recapture mobile date and the heatmap region after this change. The old-style comparison specimens may retain their historical sizing because they are visual examples, not the new control targets.

3. **Required — name the mobile return actions.** The contract calls for explicit assistant return. `mobile-assistant.png` offers only “收起”; `mobile-history.png` offers an isolated right chevron whose accessible name is “收起历史”. Give mobile users visible “返回预览” and “返回对话” actions, respectively, and matching accessible names. Preserve their existing focus-return behavior and the compact desktop collapse controls. Recapture the two mobile pane headers with the conversation check above.

After these repairs and targeted evidence, the disposition can become **ship** for the isolated preview. Until then, neither functional pass counts nor the welcome-state screenshots justify a ship verdict.

## Keep

- Preserve the selected B toolbar, old/new comparison, silver-blue background, navy primary action, pale blue selection, and existing typography.
- Preserve the date-only preset/calendar/apply model and its explicit draft-versus-applied behavior.
- Preserve rounded red cells, directly readable counts, deterministic shared event data, clear synthetic labels, and list drill-down.
- Preserve thin invisible resize separators and quiet history rows; fix the message namespace rather than adding overlay workarounds.
- Keep the production homepage and statistics implementation outside this preview review and change scope.
