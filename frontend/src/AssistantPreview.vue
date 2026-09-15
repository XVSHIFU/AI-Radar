<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { translate as tr, locale, setLocale } from './locale';
import { activeTheme, applyTheme, themes } from './themes';
import Concept from './preview/AssistantConcept.vue';
import './preview/assistant-preview.css';
const route=useRoute(), router=useRouter();
const concepts = computed(()=>[
  {id:'desk',letter:'A',name:tr('侧栏阅读','Reading sidebar'),lead:tr('让回答成为主角','Let the answer lead'),description:tr('短问题靠右，长回答舒展排开。底部独立输入台，用浅主题底色与正文拉开层次。','A short question on the right; an open reading column for the answer. A tinted dock separates the composer.'),risk:tr('最适合现在的并排助手；同时显示的资料较少。','Best fit for the current sidebar; less source material remains visible.')},
  {id:'bubble',letter:'B',name:tr('轻气泡对话','Soft conversation'),lead:tr('每一轮，清楚分开','A clear rhythm for each turn'),description:tr('问题与回答形成错落的对话块，工具放在顶部，输入区悬在底部留白中。','Offset question and answer bubbles; tools in the header and a composer resting above the bottom edge.'),risk:tr('短问短答更亲切；长回答会增加滚动。','Friendly for quick exchanges; long answers require more scrolling.')},
  {id:'evidence',letter:'C',name:tr('证据优先','Evidence first'),lead:tr('回答与依据，一步切换','One step from answer to evidence'),description:tr('固定的对话／证据双页签，当前资料始终可见。引用点击后在同一阅读区核查。','Persistent conversation and evidence tabs keep the selected material in view. Citations open in the same reading area.'),risk:tr('核查路径最明确；顶部占用略多。','The clearest verification path; more space is used above the answer.')},
  {id:'workspace',letter:'D',name:tr('上下工作区','Split workspace'),lead:tr('资料在上，讨论在下','Material above, discussion below'),description:tr('把当前事件展开成一个资料区，下面连续讨论。像工作台，适合围绕单个事件深入研究。','An expanded material area above an ongoing discussion. A workspace for focused research into one event.'),risk:tr('适合宽一些的助手；小屏需收起资料内容。','Works best in a wider panel; material must collapse on small screens.')},
  {id:'timeline',letter:'E',name:tr('对话时间线','Conversation timeline'),lead:tr('沿着问题，看见思考的顺序','Follow the thread of a question'),description:tr('延续首页的细线节奏，问题、回答与来源沿同一轴排列。输入区像页尾的续写栏。','A fine line echoes the homepage. Questions, answers and sources share one axis, ending in a writing area.'),risk:tr('与首页最统一；聊天软件的气泡感较弱。','Closest to the homepage; less like a conventional chat app.')},
  {id:'note',letter:'F',name:tr('浮动便笺','Floating notebook'),lead:tr('轻轻打开，随手追问','Open lightly, ask naturally'),description:tr('整块助手与页面保留一圈间距，资料压缩为细条。问题在上，便笺式输入台在下。','An inset assistant with breathing room around it. A narrow material strip and a notebook-like composer.'),risk:tr('最轻巧；同样宽度下可用阅读空间略少。','The lightest presence; slightly less reading space at the same width.')},
]);
const selected=computed(()=>concepts.value.find(c=>c.id===route.query.layout)||concepts.value[0]!);
const scene=ref('answer'), wide=ref(false);
function choose(id:string){router.replace({query:{...route.query,layout:id}});}
</script>
<template>
  <div class="assistant-design-lab">
    <header class="al-title"><div><h1>{{tr('研究助手，六种打开方式','Six ways to research')}}</h1><p>{{tr('同一主题，同一字体，不同布局。先试交互，再选最顺手的一种。','One theme, one type system, six layouts. Try the interactions before choosing.')}}</p></div><RouterLink to="/">{{tr('返回首页','Back to events')}}</RouterLink></header>
    <nav class="al-options" :aria-label="tr('助手布局方案','Assistant concepts')"><button v-for="c in concepts" :key="c.id" :aria-pressed="selected.id===c.id" @click="choose(c.id)"><span>{{c.letter}}</span>{{c.name}}</button></nav>
    <div class="al-workbench">
      <section class="al-explanation"><h2>{{selected.lead}}</h2><p>{{selected.description}}</p><p class="al-tradeoff">{{selected.risk}}</p>
        <div class="al-controls"><label>{{tr('预览状态','Preview state')}}<select v-model="scene"><option value="answer">{{tr('已有回答','Answered')}}</option><option value="empty">{{tr('空会话','Empty')}}</option><option value="stream">{{tr('生成中','Generating')}}</option><option value="history">{{tr('历史会话','History')}}</option><option value="error">{{tr('连接中断','Interrupted')}}</option></select></label><label>{{tr('主题配色','Theme')}}<select :value="activeTheme.id" @change="applyTheme(themes.find(t=>t.id===($event.target as HTMLSelectElement).value)!)"><option v-for="theme in themes" :key="theme.id" :value="theme.id">{{theme.name}}</option></select></label><label>{{tr('界面语言','Language')}}<select :value="locale" @change="setLocale(($event.target as HTMLSelectElement).value as 'zh'|'en')"><option value="zh">中文</option><option value="en">English</option></select></label><label class="al-width"><input type="checkbox" v-model="wide"/>{{tr('加宽阅读','Wider reading')}}</label></div>
        <p class="al-note">{{tr('可以输入、发送、停止、打开引用和历史。所有回答均为界面演示，不产生 API 用量。','Type, send, stop, open citations and history. All answers are interface demos with no API usage.')}}</p>
        <details class="al-references"><summary>{{tr('设计依据与调研','Research & design rationale')}}</summary><p>{{tr('直接观察了 Gemini 未登录网页版：居中输入区、工具与模式分组、独立侧边导航。其他产品的聊天页受登录或安全验证限制，以下采用官方资料，不冒充已查看登录后的最新版。','Observed the signed-out Gemini web app: centered composer, grouped tools and mode controls, separate navigation. Other chat apps required login or verification; the following are official references, not claims about their latest signed-in UI.')}}</p><ul><li><a href="https://gemini.google.com/app" target="_blank" rel="noreferrer">Gemini Web</a> — {{tr('输入区与工具分组','Composer and grouped tools')}}</li><li><a href="https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them" target="_blank" rel="noreferrer">Claude Artifacts</a> — {{tr('对话与独立工作区','Conversation and separate workspace')}}</li><li><a href="https://www.perplexity.ai/help-center/en/articles/10352895-how-does-perplexity-work" target="_blank" rel="noreferrer">Perplexity</a> — {{tr('回答与来源核查','Answers and source verification')}}</li><li><a href="https://gemini.google/overview/canvas/" target="_blank" rel="noreferrer">Gemini Canvas</a> — {{tr('资料与任务区域','Material and task areas')}}</li><li><a href="https://openai.com/index/introducing-canvas/" target="_blank" rel="noreferrer">ChatGPT Canvas</a> — {{tr('历史设计参考：并排协作','Historical design reference: side-by-side work')}}</li></ul></details>
      </section>
      <div class="al-preview" :class="{'al-wide':wide}"><Concept :layout="selected.id" :scene="scene"/></div>
    </div>
  </div>
</template>
