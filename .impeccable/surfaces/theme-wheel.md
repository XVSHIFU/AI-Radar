# Global theme wheel
Target: frontend/src/ThemeWheel.vue, frontend/src/themes.ts, frontend/src/themes.css.
Mode: Operate. Extend the approved five light palettes to sixteen; preserve the existing reading layout.
THESIS: A small quarter wheel offers many quiet atmospheres without moving content or confusing colors with data.
FORM: Navigation-footer entry. The quarter arc shows neighboring swatches; drag/wheel/arrows browse, click or Enter applies. Active swatch checkmark and explicit applied label preserve meaning without color alone.
MOTION: One 650ms reveal travels from the chosen swatch across the actual page. No continuous theme animation. Reduced-motion/unsupported browsers update directly.
STATE: Local browser preference, invalid-key fallback, denied-storage notice, cross-tab sync, latest selection wins. Outside click and Escape dismiss; focus restored and background protected while open.
FINISH: Desktop/mobile inspected in two bounded rounds. Contrast corrected for four sidebar secondary colors. Functional checks and final report at docs/theme-wheel-report.md. No shipping raster assets.


2026-09-14：轮盘新增160ms退出动画，向左下轻移10px、缩至86%并淡出；减少动态时改为80ms纯淡出。动画期间保留背景保护，完成后恢复焦点。桌面/手机的按钮、Escape、空白处关闭及减弱动态均通过浏览器检查；构建通过。
