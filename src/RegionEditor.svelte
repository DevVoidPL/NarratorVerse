<script lang="ts">
 import type {Rect} from './ipc';
 import Icon from './Icon.svelte';
 import {labels as t} from './i18n';
 export let image:string;
 export let initial:Rect;
 export let save:(rect:Rect)=>void;
 export let close:()=>void;
 export let saving=false;
 let region:Rect|null = {...initial};
 let zoom=1;
 let box:HTMLDivElement;
 let drag:{kind:string; x:number;y:number;rect:Rect}|null=null;
 $: valid=!!region&&Object.values(region).every(Number.isFinite)&&region.x>=0&&region.y>=0&&region.width>0&&region.height>0&&region.x+region.width<=1&&region.y+region.height<=1;
 function down(e:PointerEvent,kind='draw') {
   e.preventDefault(); e.stopPropagation();
   const b=box.getBoundingClientRect();
   const x=Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),y=Math.max(0,Math.min(1,(e.clientY-b.top)/b.height));
    if(kind==='draw') region={x:Math.min(.998,x),y:Math.min(.998,y),width:.002,height:.002};
   drag={kind,x,y,rect:{...region!}};
   box.setPointerCapture(e.pointerId);
 }
 function move(e:PointerEvent) {
   if(!drag) return;
   const b=box.getBoundingClientRect();
   const x=Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),y=Math.max(0,Math.min(1,(e.clientY-b.top)/b.height));
   const r=drag.rect,dx=x-drag.x,dy=y-drag.y;
   if(drag.kind==='move') region={...r,x:Math.max(0,Math.min(1-r.width,r.x+dx)),y:Math.max(0,Math.min(1-r.height,r.y+dy))};
   else if(drag.kind==='resize') region={...r,width:Math.max(.002,Math.min(1-r.x,r.width+dx)),height:Math.max(.002,Math.min(1-r.y,r.height+dy))};
    else {
      const left=Math.min(.998,x,drag.x),top=Math.min(.998,y,drag.y);
      region={x:left,y:top,width:Math.min(1-left,Math.max(.002,Math.abs(x-drag.x))),height:Math.min(1-top,Math.max(.002,Math.abs(y-drag.y)))};
    }
 }
</script>
<div class="modal-backdrop">
  <div class="modal region-modal" role="dialog" aria-modal="true" aria-label={t.editor} tabindex="-1">
  <header><div><h2>{t.editor}</h2><p>{t.draft}</p></div><button on:click={close}><Icon name="close"/> {t.close}</button></header>
  <div class="editor-toolbar"><label>{t.zoom}<input type="range" min="1" max="3" step=".1" bind:value={zoom}/><output>{Math.round(zoom*100)}%</output></label><button on:click={()=>region={x:.05,y:.62,width:.9,height:.3}}>{t.editorReset}</button><button on:click={()=>region=null}>{t.clear}</button></div>
  <div class="editor-scroll">
   <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
   <div class="frame" bind:this={box} style:width={`${zoom*100}%`} role="img" aria-label={t.region} on:pointerdown={e=>down(e)} on:pointermove={move} on:pointerup={()=>drag=null} on:pointercancel={()=>drag=null}>
    <img src={image} alt={t.region} draggable="false"/>
    {#if region}
     <!-- svelte-ignore a11y_no_static_element_interactions -->
     <div class="selection" style:left={`${region.x*100}%`} style:top={`${region.y*100}%`} style:width={`${region.width*100}%`} style:height={`${region.height*100}%`} on:pointerdown={e=>down(e,'move')}>
      <span class="selection-label">{t.region}</span><button class="resize-handle" aria-label={t.region} on:pointerdown={e=>down(e,'resize')}><Icon name="resize" size={15}/></button>
     </div>
    {/if}
   </div>
  </div>
  {#if region}<div class="region-numbers">{#each [['x','Od lewej'],['y','Od góry'],['width','Szerokość'],['height','Wysokość']] as [key,label]}<label>{label}<input type="number" min="0" max="1" step=".001" value={region[key as keyof Rect]} on:change={e=>{if(region){region={...region,[key]:Number(e.currentTarget.value)};}}}/></label>{/each}</div>{/if}
  {#if region&&!valid}<p role="alert">Obszar musi mieć dodatnią szerokość i wysokość oraz mieścić się w obrazie.</p>{/if}
  <footer><button disabled={saving} on:click={close}>{t.cancel}</button><button class="primary" disabled={!valid||saving} on:click={()=>valid&&region&&!saving&&save(region)}><Icon name="check"/> {saving?'Zapisywanie…':'Zatwierdź obszar'}</button></footer>
  </div>
</div>