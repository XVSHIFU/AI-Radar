<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { translate as tr } from '../locale';
import Icon from './AssistantIcon.vue';
const props = defineProps<{ layout: string; scene: string }>();
const question = computed(() => tr('这条事件的关键变化是什么？', 'What is the key change in this event?'));
const answer = computed(() => tr('先看变化，再回到证据。\n\n研究助手会围绕选中的事件整理要点，并在相关句子旁保留引用入口。打开引用，可以核对保存的原文段落。\n\n这段文字用于比较排版和阅读体验，是界面演示，不是模型对事件的实际分析。', 'Start with the change, then return to the evidence.\n\nThe assistant organizes the selected event and keeps source links beside relevant statements. Open a citation to inspect its saved passage.\n\nThis text demonstrates layout and reading rhythm. It is not an actual model analysis.'));
const draft = ref(''), asked = ref(''), reply = ref(''), status = ref('');
const running = ref(false), history = ref(false), sources = ref(false), scope = ref(false), attached = ref(true), closed = ref(false), away = ref(false);
const viewport = ref<HTMLElement>();
let timer: ReturnType<typeof setInterval> | undefined;
function stop() { if(timer) clearInterval(timer); timer=undefined; running.value=false; }
function reset(scene=props.scene) {
  stop(); history.value=false; sources.value=false; closed.value=false; status.value=''; away.value=false;
  asked.value=scene==='empty'?'':question.value; reply.value=scene==='empty'?'':answer.value;
  if(scene==='history') history.value=true;
  if(scene==='error') { reply.value=''; status.value=tr('连接中断。已保留问题，可以重试。','Connection interrupted. Your question is kept; you can retry.'); }
  if(scene==='stream') stream();
}
function latest() { away.value=false; nextTick(()=>viewport.value?.scrollTo({top:viewport.value.scrollHeight,behavior:'smooth'})); }
function stream() {
  stop(); reply.value=''; running.value=true; status.value='';
  let i=0; timer=setInterval(()=>{ i+=5; reply.value=answer.value.slice(0,i); if(!away.value) nextTick(()=>{ if(viewport.value) viewport.value.scrollTop=viewport.value.scrollHeight; }); if(i>=answer.value.length) stop(); },100);
}
function send() { if(!draft.value.trim() || running.value) return; asked.value=draft.value.trim(); draft.value=''; stream(); latest(); }
function cancel() { stop(); status.value=tr('已停止生成。','Generation stopped.'); }
function selectHistory(label:string) { stop(); asked.value=label; reply.value=answer.value; status.value=''; history.value=false; latest(); }
function newChat() { draft.value=''; reset('empty'); }
function scroll() { const el=viewport.value; if(el) away.value=el.scrollHeight-el.scrollTop-el.clientHeight>50; }
watch(()=>[props.layout,props.scene],()=>reset(),{immediate:true});
onBeforeUnmount(stop);
</script>
<template>
  <div class="ac-frame" :class="['ac-'+layout, {'ac-is-empty':!asked,'ac-has-history':history}]">
    <button v-if="closed" class="ac-reopen" @click="closed=false"><Icon name="chat"/>{{tr('打开研究助手','Open research assistant')}}</button>
    <section v-else class="ac-panel" :aria-label="tr('助手布局交互预览','Assistant layout preview')">
      <header class="ac-header"><span class="ac-mark"><Icon :name="layout==='timeline'?'book':'chat'"/></span><div class="ac-heading"><strong>{{tr('研究助手','Research assistant')}}</strong><span>{{tr('布局演示','Layout demo')}}</span></div><div class="ac-header-actions">
        <button class="ac-icon" :title="tr('历史会话','Conversations')" :aria-label="tr('历史会话','Conversations')" :aria-expanded="history" @click="history=!history"><Icon name="history"/></button><button class="ac-icon" :title="tr('新建会话','New conversation')" :aria-label="tr('新建会话','New conversation')" @click="newChat"><Icon name="plus"/></button><button class="ac-icon" :title="tr('收起助手','Close assistant')" :aria-label="tr('收起助手','Close assistant')" @click="closed=true"><Icon name="chevron"/></button>
      </div></header>
      <div class="ac-scope-row"><button class="ac-scope-toggle" :aria-expanded="scope" @click="scope=!scope"><Icon name="scope"/>{{tr('当前事件','Selected event')}}<Icon name="down"/></button><span>{{tr('仅使用库内资料','Library sources only')}}</span></div>
      <div v-if="scope" class="ac-scope-detail">{{tr('本次预览使用合成段落，不发送请求，也不读取或改变你的历史会话。','This preview uses sample passages. It sends no requests and does not access your conversations.')}}</div>
      <nav v-if="layout==='evidence'" class="ac-tabs" :aria-label="tr('内容切换','Content view')"><button :aria-pressed="!sources" @click="sources=false"><Icon name="chat"/>{{tr('对话','Conversation')}}</button><button :aria-pressed="sources" @click="sources=true"><Icon name="book"/>{{tr('来源与证据','Sources & evidence')}} <span>1</span></button></nav>
      <section v-if="attached" class="ac-attachment"><Icon name="document"/><div><span>{{layout==='workspace'?tr('正在研究的资料','Research material'):tr('已加入事件','Attached event')}}</span><strong>{{tr('AI 事件与来源核查','AI event and source review')}}</strong><p v-if="layout==='workspace'">{{tr('将资料放在手边，边读边问。','Keep the material in view as you ask.')}}</p></div><button class="ac-icon" :title="tr('移除事件','Remove event')" :aria-label="tr('移除事件','Remove event')" @click="attached=false"><Icon name="close"/></button></section>
      <div class="ac-body">
        <aside v-if="history" class="ac-history"><div><strong>{{tr('历史会话','Conversations')}}</strong><button class="ac-icon" :aria-label="tr('关闭历史','Close history')" @click="history=false"><Icon name="close"/></button></div><button v-for="(label,i) in [tr('事件要点与证据','Event highlights & evidence'),tr('模型发布回顾','Model release review'),tr('智能体工具观察','Agent tool notes')]" :key="i" @click="selectHistory(label)"><Icon name="chat"/><span>{{label}}</span></button><small>{{tr('此处为预览历史','Preview history only')}}</small></aside>
        <div ref="viewport" class="ac-thread" @scroll="scroll">
          <section v-if="sources" class="ac-evidence-view"><div class="ac-evidence-title"><Icon name="book"/><h3>{{tr('来源与证据','Sources & evidence')}}</h3><button class="ac-icon" :aria-label="tr('返回对话','Back to conversation')" @click="sources=false"><Icon name="close"/></button></div><strong>{{tr('示例：保存的来源段落','Sample: saved source passage')}}</strong><blockquote>{{tr('这是一段用于界面设计的合成引文，用来展示原文核查区域的间距和阅读层次。','A sample quotation for interface design, showing spacing and hierarchy in the evidence view.')}}</blockquote><p>{{tr('不可变版本 · 段落 p-001 · 演示','Immutable version · passage p-001 · Demo')}}</p></section>
          <template v-else><div v-if="!asked" class="ac-empty"><Icon :name="layout==='evidence'?'book':'chat'"/><h3>{{tr('从一个问题开始','Start with a question')}}</h3><p>{{tr('读懂变化，找到依据。','Understand the change. Find the evidence.')}}</p><button @click="draft=question">{{tr('这条事件有哪些要点？','What are the highlights?')}}<Icon name="chevron"/></button></div><template v-else>
            <article class="ac-message ac-user"><div class="ac-role">{{tr('你','You')}}</div><p>{{asked}}</p></article>
            <article v-if="reply||running" class="ac-message ac-answer"><div class="ac-role"><Icon name="chat"/><strong>{{tr('研究助手','Research assistant')}}</strong><span v-if="running">{{tr('正在生成','Generating')}}</span></div><div class="ac-answer-text"><p v-for="(p,i) in reply.split('\n\n')" :key="i">{{p}}<button v-if="i===1" class="ac-citation" :aria-label="tr('查看引用 1','View citation 1')" @click="sources=true">1</button><span v-if="running&&i===reply.split('\n\n').length-1" class="ac-caret"></span></p></div><button v-if="!running" class="ac-source-link" @click="sources=true"><Icon name="book"/>{{tr('1 个来源 · 查看证据','1 source · View evidence')}}<Icon name="chevron"/></button></article>
          </template></template>
        </div><button v-if="away&&!sources" class="ac-icon ac-latest" :class="{'is-running':running}" :title="tr('回到最新消息','Jump to latest')" :aria-label="tr('回到最新消息','Jump to latest')" @click="latest"><Icon name="down"/></button>
      </div>
      <footer class="ac-dock"><p v-if="status" class="ac-status" role="status">{{status}} <button v-if="scene==='error'" @click="stream">{{tr('重试','Retry')}}</button></p>
        <form class="ac-composer" @submit.prevent="send"><label class="ac-sr-only" :for="'ac-input-'+layout">{{tr('输入问题','Your question')}}</label><textarea :id="'ac-input-'+layout" v-model="draft" rows="2" :placeholder="tr('对这条事件提问…','Ask about this event…')" @keydown.enter.exact.prevent="send"/><div class="ac-toolbar"><button type="button" class="ac-icon" :title="tr('添加或移除事件','Attach or remove event')" :aria-label="tr('添加或移除事件','Attach or remove event')" :aria-pressed="attached" @click="attached=!attached"><Icon name="plus"/></button><button type="button" class="ac-icon" :title="tr('查看研究范围','View research scope')" :aria-label="tr('查看研究范围','View research scope')" @click="scope=!scope"><Icon name="filter"/></button><span>{{tr('库内研究','Library research')}}</span><button class="ac-icon ac-send" :type="running?'button':'submit'" :aria-disabled="!running&&!draft.trim()" :title="running?tr('停止生成','Stop generation'):draft.trim()?tr('发送问题','Send question'):tr('请输入你的问题','Enter a question')" :aria-label="running?tr('停止生成','Stop generation'):tr('发送问题','Send question')" @click="running&&cancel()"><Icon :name="running?'stop':'send'"/></button></div></form><p class="ac-footnote">{{tr('演示交互 · 不调用模型', 'Preview interaction · No model calls')}}</p>
      </footer>
    </section>
  </div>
</template>
