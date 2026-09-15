import { ref } from 'vue';

// Original vector studies. Preview selection never changes the saved product theme.
export const brandStudies = [
  { id: 'signal', name: '01 · 信号刻度', note: '一个信号点，三段向外扩展的刻度。轻、清楚，最接近雷达本意。', paths: ['M16 4a12 12 0 0 1 12 12M16 9a7 7 0 0 1 7 7M16 14l8-8M10 5a12 12 0 1 0 17 17'], dots: [[16,16,2]] },
  { id: 'orbit', name: '02 · 轨道交汇', note: '两条轨道共享一个中心，表达不同信息来源在此汇合。', paths: ['M5 12C9 3 23 3 27 12S23 29 15 26S2 19 5 12Z', 'M12 5C3 9 3 23 12 27S29 23 26 15S19 2 12 5Z'], dots: [[16,16,2]] },
  { id: 'thread', name: '03 · 时间脉络', note: '贯穿的主线与三个节点，直接呼应你保留的时间线。', paths: ['M11 3v26M11 8h13M11 23h9'], dots: [[11,8,2.4],[11,16,2.4],[11,24,2.4]] },
  { id: 'aperture', name: '04 · 观察窗口', note: '开放的窗口与一个发现点。轮廓稳，缩成标签页也容易辨认。', paths: ['M13 5H7a2 2 0 0 0-2 2v6M19 5h6a2 2 0 0 1 2 2v6M27 19v6a2 2 0 0 1-2 2h-6M13 27H7a2 2 0 0 1-2-2v-6M10 22l9-9'], dots: [[21,11,3]] },
  { id: 'horizon', name: '05 · 新知地平线', note: '地平线上升起的新信号，柔和、有开放感，适合公众阅读。', paths: ['M4 24h24M7 19a9 9 0 0 1 18 0M16 3v3M5 8l2 2M27 8l-2 2'], dots: [[16,18,2]] },
  { id: 'lens', name: '06 · 聚焦', note: '一圈聚焦框与向前的视线。简单、有方向感，科技感克制。', paths: ['M23 7a12 12 0 1 0 2 16M16 16l11-11M20 5h7v7'], dots: [[16,16,2.4]] },
  { id: 'leaves', name: '07 · 生长分支', note: '一条主干衍生两支新知，温和、有机，适合暖色主题。', paths: ['M16 28V16M16 18C6 18 4 10 5 5c7 0 11 5 11 13ZM16 23c9 0 12-7 11-12-7 0-11 4-11 12Z'], dots: [] },
  { id: 'relay', name: '08 · 知识接力', note: '两个相扣的开放环，强调证据、来源与事件之间的联系。', paths: ['M18 9l2-2a6 6 0 0 1 9 8l-6 6a6 6 0 0 1-9 0M14 23l-2 2a6 6 0 0 1-9-8l6-6a6 6 0 0 1 9 0M11 21l10-10'], dots: [] },
];
export const previewBrand = ref('thread');
