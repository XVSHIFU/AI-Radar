<script setup lang="ts">
import { ref } from 'vue';
import { useRoute } from 'vue-router';
import { tx } from './reading-locale';
import DateRangePicker from './DateRangePicker.vue';
import './type-preview.css';
const route = useRoute();
const selected = ref('clear');
const range = ref({ from: '', to: '' });
const studies = [
  { id:'clear', name:'A · 清晰黑体', en:'A · Clear sans', pair:'Noto Sans SC × Inter', note:'标题与正文都用黑体。利落、清楚，适合长时间扫描事件。', enNote:'Sans serif throughout. Clear and direct for scanning a long event feed.' },
  { id:'editorial', name:'B · 杂志标题', en:'B · Editorial', pair:'Noto Serif SC / Source Serif 4 + Noto Sans SC / Inter', note:'宋体标题搭配黑体正文。保留杂志感，正文依然轻快。', enNote:'Serif headlines with sans serif body copy. Editorial character with an easy reading rhythm.' },
  { id:'literary', name:'C · 书刊宋体', en:'C · Bookish serif', pair:'Noto Serif SC × Source Serif 4', note:'标题和摘要都用宋体。层次安静，更接近书刊的阅读感。', enNote:'Serif headlines and summaries. A quieter, book-like reading experience.' },
  { id:'warm', name:'D · 温润楷体', en:'D · Warm humanist', pair:'LXGW WenKai × Source Serif 4', note:'中文使用霞鹜文楷。字形舒展、温和，适合慢一些的阅读。', enNote:'LXGW WenKai for Chinese, paired with Source Serif 4. Warm and relaxed for slower reading.' },
  { id:'distinct', name:'E · 小薇标题', en:'E · Distinctive serif', pair:'ZCOOL XiaoWei / Source Serif 4 + Noto Sans SC / Inter', note:'小薇体只用于标题。带一点独特的笔形，正文仍用清楚的黑体。', enNote:'ZCOOL XiaoWei adds character to headings; neutral sans serif body copy keeps the text clear.' },
];
</script>
<template>
  <section class="type-lab">
    <header class="type-lab-header"><div><h1>{{ tx('找到舒服的阅读字体', 'Find your reading voice') }}</h1><p>{{ tx('同一份内容，五种中英文搭配。只切换这里的预览，不修改当前全站字体。', 'The same text in five Chinese–English pairings. Changes apply only to this preview.') }}</p></div><RouterLink :to="{ path:'/', query:route.query.demo==='1'?{demo:'1'}:{} }">{{ tx('返回首页', 'Back to home') }}</RouterLink></header>
    <div class="type-options" role="group" :aria-label="tx('字体方案', 'Typeface options')"><button v-for="s in studies" :key="s.id" :aria-pressed="selected===s.id" @click="selected=s.id">{{ tx(s.name,s.en) }}</button></div>
    <p class="type-pair">{{ studies.find(s=>s.id===selected)?.pair }}</p>
    <p class="type-description">{{ tx(studies.find(s=>s.id===selected)!.note,studies.find(s=>s.id===selected)!.enNote) }}</p>
    <div class="type-specimens" :data-type="selected">
      <article class="type-specimen" lang="zh-CN"><div class="type-specimen-label">中文阅读</div><div class="type-mini-meta"><span>模型发布</span><time>2026 年 9 月 15 日</time></div><h2>把每天的 AI 进展，串成一条清楚的时间线</h2><p class="type-body">新的模型、工具与研究不断出现。我们先看发生了什么，再沿着来源追查依据。好的摘要应该在几行之内说清楚重点，让你决定是否继续阅读。遇到 NVIDIA、DeepSeek、OpenAI 这样的中英文混排，字体也应该保持清楚、自然和一致。</p><p class="type-small">重要度 3/5 · 2 个来源 · 4 条关联证据</p></article>
      <article class="type-specimen" lang="en"><div class="type-specimen-label">English reading</div><div class="type-mini-meta"><span>Model releases</span><time>September 15, 2026</time></div><h2>Reading AI progress, one event at a time</h2><p class="type-body">New models, tools, and research arrive every day. Start with what happened, then follow the sources. A useful summary makes its point in a few lines and helps you decide what to read next. Mixed Chinese and English should share a clear, balanced rhythm.</p><p class="type-small">Importance 3/5 · 2 sources · 4 evidence excerpts</p></article>
      <section class="type-ui-specimen"><h2>{{ tx('放进实际控件再看一下', 'See it in working controls') }}</h2><div class="type-control-row"><label>{{ tx('关键词','Keyword') }}<input :placeholder="tx('标题、摘要、实体','Title, summary, entity')" /></label><DateRangePicker :from="range.from" :to="range.to" allow-unbounded @change="range=$event" /></div><p class="type-small">0123456789 · 1,280 · 3/5 · NVIDIA / DeepSeek / OpenAI</p></section>
    </div>
    <p class="type-lab-note">{{ tx('这是排版样本文案，非新收录事件。每组使用同样的字号和内容，方便比较字形本身；控制区保持易读的黑体。', 'These are typography samples, not newly collected events. Sizes and copy stay consistent so you can compare the letterforms; controls use readable sans serif type.') }}</p>
    <details class="type-font-sources"><summary>{{ tx('字体来源与授权','Font sources and licenses') }}</summary><p><a href="https://github.com/google/fonts" target="_blank" rel="noopener">Google Fonts</a> · <a href="https://github.com/lxgw/LxgwWenKai" target="_blank" rel="noopener">LXGW WenKai</a></p><p>{{ tx('预览字体在本地托管，按固定样本文字裁剪，不依赖第三方字体接口。', 'Preview fonts are self-hosted and subset to these fixed specimens; no external font service is used.') }} <a href="/type-studies/fonts/README.md" target="_blank" rel="noopener">{{ tx('来源清单与许可','Sources and licenses') }}</a></p></details>
  </section>
</template>
