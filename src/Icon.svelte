<script lang="ts">
 export let name:string;
 export let size=18;
 // Local, consistent 24px artwork. Decorative SVGs leave accessible names to labels.
 const shapes:Record<string,{base:string[];accent?:string[];solid?:boolean}>={
  narrator:{base:['M4 4h16v13H9l-5 4V4Z','M8 8h8M8 12h6']},
  quick:{base:['M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3ZM12 18v3M8 21h8'],accent:['M5 10v1a7 7 0 0 0 14 0v-1']},
  components:{base:['m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3ZM4 7.5l8 4.5 8-4.5M12 12v9'],accent:['m8 5.25 8 4.5v4.5']},
  settings:{base:['m10 3-.6 2.2-2 .9L5.3 5.5 3.5 8.6 5 10.2v2.3L3.5 14l1.8 3.2 2.1-.6 2 .9L10 20h4l.6-2.5 2-.9 2.1.6 1.8-3.2-1.5-1.5v-2.3l1.5-1.6-1.8-3.1-2.1.6-2-.9L14 3h-4Z'],accent:['M15 11.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z']},
  play:{base:['m8 5 11 7-11 7V5Z'],solid:true},
  pause:{base:['M7 5h3v14H7ZM14 5h3v14h-3Z'],solid:true},
  stop:{base:['M6 6h12v12H6Z'],solid:true},
  plus:{base:['M12 5v14M5 12h14']},
  edit:{base:['m15 5 4 4M5 15l-1 5 5-1L20 8a2.8 2.8 0 0 0-4-4L5 15Z'],accent:['M13 20h7']},
  trash:{base:['M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15'],accent:['M10 10v7M14 10v7']},
  close:{base:['m6 6 12 12M18 6 6 18']},
  refresh:{base:['M20 10a8 8 0 0 0-14-5L3 8M3 3v5h5M4 14a8 8 0 0 0 14 5l3-3M21 21v-5h-5']},
  reset:{base:['M3 9h5M3 9V4M3 9a9 9 0 1 1 0 7'],accent:['M12 7v5l3 2']},
  monitor:{base:['M4 3h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM12 16v5M8 21h8'],accent:['m9 7 5 3-5 3V7Z']},
  region:{base:['M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5'],accent:['M7 7h10v10H7Z']},
  save:{base:['M4 3h13l4 4v14H3V3h1ZM7 3v6h9V3'],accent:['M7 21v-8h10v8']},
  upload:{base:['M4 15v5h16v-5'],accent:['M12 16V3m-5 5 5-5 5 5']},
  download:{base:['M4 15v5h16v-5'],accent:['M12 3v13m-5-5 5 5 5-5']},
  check:{base:['M5 12l4 4L19 6']},
  chevron:{base:['m6 9 6 6 6-6']},
  voice:{base:['M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3ZM5 10v1a7 7 0 0 0 14 0v-1M12 18v3M8 21h8']},
  shield:{base:['m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z'],accent:['m8 12 3 3 5-6']},
  clear:{base:['m4 14 9-10a2 2 0 0 1 3 0l5 5a2 2 0 0 1 0 3l-8 9H9l-5-4a2 2 0 0 1 0-3ZM9 9l8 8'],accent:['M13 21h8']},
  info:{base:['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],accent:['M12 11v6M12 7v.1']},
  arrow:{base:['M5 12h14m-5-5 5 5-5 5']},
  resize:{base:['M8 20h12V8m-1 11L5 5M5 11V5h6']}
 };
 $: shape=shapes[name]||shapes.info;
</script>

<svg class="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
 {#each shape.base as d}<path {d} fill={shape.solid?'currentColor':'none'}/>{/each}
 {#each shape.accent||[] as d}<path {d}/>{/each}
</svg>