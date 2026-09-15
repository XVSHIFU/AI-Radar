# Type study font sources

These fonts are self-hosted solely for the `/type-preview` comparison page. The assets were downloaded directly from their official GitHub repositories and subset locally with fontTools; no application text was sent to a font service.

| Family | Preview asset | Style / axes | Official source | License |
| --- | --- | --- | --- | --- |
| Noto Sans SC | `noto-sans-sc.woff2` | Variable weight 100–900 | [google/fonts `ofl/notosanssc`](https://github.com/google/fonts/tree/main/ofl/notosanssc) | `licenses/OFL-Noto-Sans-SC.txt` |
| Noto Serif SC | `noto-serif-sc.woff2` | Variable weight 200–900 | [google/fonts `ofl/notoserifsc`](https://github.com/google/fonts/tree/main/ofl/notoserifsc) | `licenses/OFL-Noto-Serif-SC.txt` |
| LXGW WenKai | `lxgw-wenkai.woff2` | Regular 400, release v1.522 | [lxgw/LxgwWenKai release v1.522](https://github.com/lxgw/LxgwWenKai/releases/tag/v1.522) | `licenses/OFL-LXGW-WenKai.txt` |
| ZCOOL XiaoWei | `zcool-xiaowei.woff2` | Regular 400 | [google/fonts `ofl/zcoolxiaowei`](https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei) | `licenses/OFL-ZCOOL-XiaoWei.txt` |
| Inter | `inter.woff2` | Variable optical size 14–32, weight 100–900 | [google/fonts `ofl/inter`](https://github.com/google/fonts/tree/main/ofl/inter) | `licenses/OFL-Inter.txt` |
| Source Serif 4 | `source-serif-4.woff2` | Variable optical size 8–60, weight 200–900 | [google/fonts `ofl/sourceserif4`](https://github.com/google/fonts/tree/main/ofl/sourceserif4) | `licenses/OFL-Source-Serif-4.txt` |

## Subset coverage

These WOFF2 files contain only the characters used by the fixed `/type-preview` specimen, plus printable ASCII and common Chinese punctuation. They are preview assets, not production webfonts, and must be regenerated if the specimen text changes. The subset was produced locally from `type-specimen.txt`; no project text was uploaded to a font service.

The source TTF files are intentionally excluded from the repository. SHA-256 hashes for both upstream inputs and generated WOFF2 files are recorded in `manifest.json`.
