## verdict

All twelve required captures under `.impeccable/review/drawers/reviewer-fix-1/` were opened and visually inspected: desktop/mobile home, home-full, month-collapsed, event, source and evidence. The captures are valid and show their named states; both full-page captures include the document top. This is a scoring pass against the original four material fixes, using the supplied bounded source diff and motion evidence where still images cannot show movement.

1. **resolved — Drawer movement.** The settled event/source/evidence captures retain readable foreground planes; the bounded diff supplies the 200ms, 14px entrance/re-activation movement from an already-visible default. `docs/drawer-motion-results.json` records source movement from 658 to 644 and parent return movement from 688.34 to 676; reduced-motion records animation `none` and unchanged positions for both operations.
2. **resolved — Year disclosure composition.** Desktop and mobile home/collapsed captures now show the chevron beside the unbroken year label, the loaded count on its own subordinate line, and separation before the month tab. The former orphan indicator and collision are gone.
3. **resolved — Mobile global date controls.** Both mobile home states visibly show 展开/折叠 beside the year heading. The bounded diff removes the generated +/− substitutes, retains 全部 in the accessible labels, and sets the mobile button minimum height to 44px.
4. **resolved — Desktop rear-layer finish.** Source and evidence captures preserve the actual rear white-plane edges while removing the clipped Close buttons, notices and body-text fragments. The foreground layer remains complete; mobile captures retain the full-cover presentation and Back path.

No regressions introduced by this repair batch were found in the supplied recaptures.

## remaining

clear. This ship verdict covers the four scored fixes, not a new review of the whole surface.

disposition: ship
