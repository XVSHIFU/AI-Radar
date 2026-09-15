# Editorial fonts

Self-hosted production fonts for editorial layout. All files were built locally from official Google Fonts repository sources; no application or article text was sent to a font service.

- `RadarSansSC`: Noto Sans SC, static weights 400 and 600.
- `RadarSerifSC`: Noto Serif SC, static weight 600.
- `RadarInter`: Inter, variable weight 100–900 and optical size 14–32.
- `RadarSourceSerif`: Source Serif 4, variable weight 200–900 and optical size 8–60.

Chinese Extension A and Basic CJK are split into disjoint 512-codepoint `unicode-range` shards. Symbols, compatibility forms, and supplementary ideographs use separate shards. This covers the complete character repertoire supplied by each official source across CJK punctuation, Extension A and Basic CJK; ordinary fallback handles newer codepoints absent from an upstream font. The official Noto Sans SC source lacks the final 10 Extension A and final 16 Basic CJK codepoints, while Noto Serif SC includes every codepoint in both blocks.

Recommended body weights are 400–600 for `RadarInter` / `RadarSansSC`; titles use 600 for `RadarSourceSerif` / `RadarSerifSC`. All WOFF2 assets total 17,957,232 bytes, but a browser loads only shards containing rendered characters. A 512-codepoint Han shard averages 99,562 bytes. Exact sources and hashes are in `manifest.json`; original OFL licenses are under `licenses/`.
