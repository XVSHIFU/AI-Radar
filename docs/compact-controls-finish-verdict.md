# Compact controls preview — finish verdict

Disposition: **ship** for the isolated B lightweight-controls preview.

This closure pass scores only the three material fixes in `compact-controls-finish-review.md`. It does not reopen design direction or accept production integration, real collection, or AI generation.

| Finding | Score | Closure evidence |
|---|---|---|
| Assistant message inherits fixed shell positioning | **resolved** | Shell rules now target `#assistant`, including mobile and closed states. Updated `desktop-conversation.png` and `mobile-conversation.png` show readable messages inside their scroll region, with the assistant header and bottom composer visible. Desktop history remains unobscured. The new `reply_is_in_message_flow` and `composer_below_messages` checks pass. |
| Mobile date and heatmap targets below 44px | **resolved** | Mobile calendar cells and date inputs now have 44px height; horizontal presets give seven calendar columns sufficient width at 390px. Mobile heatmap columns have a 44px minimum and cells have 44px height inside the existing horizontal scroller. Updated `mobile-date.png` and `mobile.png` confirm the changed composition, readable dates, and retained sticky category labels. The date panel remains within the captured viewport. |
| Mobile return actions lack explicit labels | **resolved** | Updated `mobile-assistant.png` and `mobile-conversation.png` show “返回预览”; `mobile-history.png` shows “返回对话”. Source confirms matching visible/accessibility text, with desktop collapse presentation retained. |

The targeted final captures opened in this closure pass were `desktop-conversation.png`, `mobile-conversation.png`, `mobile-date.png`, `mobile.png`, `mobile-assistant.png`, and `mobile-history.png`, all under `.impeccable/review/compact-controls/`. The original eight captures were opened during the preceding review.

Recorded validation is now **20/20 interaction checks passed**, with conversation reload preservation, mobile page overflow/date containment, and tablet date containment also passing. No additional detector run or design-polish round was performed by this reviewer.

The selected B hierarchy, established silver-blue palette and typography, date-only picker, rounded red synthetic-data heatmap, and thin resize separators remain intact. All three required fixes are closed; no material fix remains from this review. Stop polishing and deliver this preview within its approved scope.
