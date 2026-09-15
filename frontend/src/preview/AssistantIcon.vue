<script setup lang="ts">
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  send: 'M12 19V5m-6 6 6-6 6 6', close: 'm6 6 12 12M6 18 18 6', plus: 'M12 5v14M5 12h14', history: 'M12 7v5l3 2',
  filter: 'M4 5h16l-6 7v5l-4 2v-7z', document: 'M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h5', chevron: 'm9 6 6 6-6 6', down: 'm6 9 6 6 6-6',
  book: 'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3zM12 6v15', chat: 'M4 4h16v12H9l-5 4zM8 8h8M8 12h5', scope: 'M4 8V4h4m8 0h4v4m0 8v4h-4M8 20H4v-4M8 12h8M12 8v8',
};
</script>
<template><svg viewBox="0 0 24 24" aria-hidden="true"><circle v-if="name==='history'" cx="12" cy="12" r="8"/><rect v-if="name==='stop'" x="7" y="7" width="10" height="10" rx="1" fill="currentColor" stroke="none"/><path v-else :d="paths[name] || paths.chat"/></svg></template>
