import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
const router=createRouter({history:createWebHistory(),routes:[{path:'/',component:()=>import('./HomePage.vue')},{path:'/events/:id',component:()=>import('./DetailPage.vue')},{path:'/ask',component:()=>import('./AskPage.vue')},{path:'/ingest',component:()=>import('./IngestPage.vue')}]})
createApp(App).use(router).mount('#app')
