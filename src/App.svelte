<script lang="ts">
 import {onMount} from 'svelte';
 import {listen} from '@tauri-apps/api/event';
 import {rpc,type Profiles,type Component,type Rect} from './ipc';
 import {labels as t} from './i18n';
 import {ui as u} from './ui';
 import {adaptiveLabels as a} from './adaptive';
 import {audioBalanceLabels as b} from './audioBalance';
 import {createDraft,receiveProfile,editDraft,editOcr,isDirty,savePayload,savedMatches,type Draft} from './profileDraft';
 import logo from '../data/icons/64x64.png';
 import RegionEditor from './RegionEditor.svelte';
 import Icon from './Icon.svelte';

 let tab:'main'|'quick'|'components'='main';
 let profiles:Profiles|null=null,session:any=null,components:Component[]=[];
 let error='',notice='',pending=0,ready=false;
 let editorImage='',editor=false,download:any=null;
 let profileDialog:''|'create'|'rename'='',profileName='';
 let confirmAction:(()=>void)|null=null,confirmText='';
 let log:any[]=[];
 let form:Draft|null=null;
 let voiceMenu=false;
 let quick:any={state:'idle',options:{voice_id:'voidek-pl-e991',speech_rate:1,volume:.85}};
 let quickText=localStorage.getItem('quick-text')??u.example;
 let quickOptions={voice_id:'voidek-pl-e991',speech_rate:1,volume:.85};
 let quickDirty=false;
 let audioTargets:{target:string;label:string;ambiguous:boolean}[]=[],audioLoading=false,audioLoaded=false,audioError='';
 $: profile=profiles?.profiles.find(p=>p.id===profiles?.selected);
 $: if(profile)form=receiveProfile(form,profile);
 $: draft=form?.values||{};
 $: dirty=!!form&&isDirty(form);
 $: active=!!session?.active;
 $: snap=session?.snapshot||{};
 $: busy=pending>0;
 $: quickBusy=['synthesizing','playing','stopping'].includes(quick.state);
 $: sessionState=session?.ui_state||'empty';
 $: voiceName=profiles?.voices.find(v=>v.voice_id===(draft.voice_id||'voidek-pl-e991'))?.name||'Voidek';
 $: locked=active||busy;
 const numberFields=[['capture_sampling_hz','sampling',1,10,.5],['visual_change_threshold','threshold',.001,1,.001],['stabilization_ms','stabilization',50,3000,10],['ocr_min_confidence','confidence',0,1,.01],['duplicate_cooldown_ms','cooldown',250,60000,50]] as const;

 function text(key:string,dictionary:Record<string,string>){return dictionary[key]||key;}
 async function action(method:string,params:Record<string,unknown>={},blocking=true) {
   error='';notice='';if(blocking)pending++;
   try {
     const result=await rpc(method,params);
     if(method==='component'&&params.action==='verify')notice=result[0]?u.verifyOK:u.verifyFailed+': '+result[1];
     return result;
   } catch(e){error=String(e);return undefined;}
   finally{if(blocking)pending--;}
 }
 function applyStatus(data:any){profiles=data.profiles;components=data.components;session=data.session;receiveQuick(data.quick_read);ready=true;}
 async function load(){const data=await action('status',{},false);if(data)applyStatus(data);}
 function confirm(message:string,fn:()=>void){confirmText=message;confirmAction=fn;}
 function edit(key:string,value:unknown){if(form){form=editDraft(form,key,value);notice='';}}
 function discard(){if(profile)form=createDraft(profile);notice='';}
 async function saveDraft(){
   if(!form||!isDirty(form)||active||pending>0)return;
   const submitted=form;
   error='';notice='';pending++;
   try{
     await rpc('settings',savePayload(submitted));
     const data=await rpc('status');
     const saved=data.profiles.profiles.find((item:any)=>item.id===submitted.profileId);
     if(!saved||data.profiles.selected!==submitted.profileId||!savedMatches(submitted,saved))throw new Error(u.saveFailed);
     applyStatus(data);form=createDraft(saved);notice=t.saved;
   }catch(e){error=String(e);}
   finally{pending--;}
 }
 async function profileAction(method:string,params:Record<string,unknown>={}):Promise<boolean>{
   if(form&&isDirty(form)){confirm(u.unsaved+' — '+u.discard+'?',()=>{discard();void profileAction(method,params);});return false;}
   const result=await action(method,params);
   if(result===undefined)return false;
   const data=await action('status',{},false);
   if(!data)return false;
   applyStatus(data);voiceMenu=false;return true;
 }
 async function submitProfile(){
   const method=profileDialog==='create'?'profile_create':'profile_rename';
   // Close first: an unsaved-change confirmation must not leave two dialogs stacked.
   profileDialog='';await profileAction(method,{name:profileName});
 }
 async function resetSection(section:string){
   if(form&&isDirty(form)){confirm(u.unsaved+' — '+u.discard+'?',()=>{discard();void resetSection(section);});return;}
   confirm(section==='profile'?t.profileReset:t.sectionReset,()=>void resetNow(section));
 }
 async function resetNow(section:string){
   if(await action('reset',{section})){
     const data=await action('status',{},false);
     if(data){applyStatus(data);notice=t.saved;}
   }
 }
 async function refreshAudio(){
   if(audioLoading)return;audioLoading=true;audioError='';
   try{audioTargets=await rpc<typeof audioTargets>('audio_targets');audioLoaded=true;}
   catch(e){audioTargets=[];audioLoaded=false;audioError=String(e);}
   finally{audioLoading=false;}
 }
 function receiveQuick(data:any){if(!data)return;quick=data;if(!quickDirty)quickOptions={...data.options};}
 async function saveQuick(){quickDirty=true;const result=await action('quick_settings',{values:quickOptions});if(result){quickDirty=false;receiveQuick(result);}}
 async function readQuick(){quickDirty=true;const result=await action('quick_read',{text:quickText,options:quickOptions});if(result){quickDirty=false;receiveQuick(result);}else quickDirty=false;}
 async function applyQuickToProfile(){
   if(!form)return;
   for(const key of ['voice_id','speech_rate','volume'] as const)form=editDraft(form,key,quickOptions[key]);
   await saveDraft();
 }
 async function primary(){
   if(sessionState==='reading')await action('pause');
   else if(dirty){error='Zapisz lub odrzuć zmiany profilu przed rozpoczęciem sesji.';}
   else if(!active||sessionState==='failed')await action('start');
   else if(session?.has_frame&&!session.region_confirmed)await action('preview');
   else if(session?.has_frame)await action('read');
 }
 async function saveRegion(rect:Rect){if(await action('region',{rect})){editor=false;notice='Obszar napisów zapisany.';}}
 onMount(()=>{
   let unlisten:(()=>void)|undefined,disposed=false;
   void listen<any>('backend',({payload})=>{
     const d=payload.data;
     if(payload.event==='ready'){ready=true;void load();}
     else if(payload.event==='session'){session=d;if(!d.active){editor=false;editorImage='';}}
     else if(payload.event==='profiles')profiles=d;
     else if(payload.event==='components')components=d;
     else if(payload.event==='quick_read')receiveQuick(d);
     else if(payload.event==='preview'){editorImage=d.imageUrl;editor=true;}
     else if(payload.event==='download')download=d;
     else if(payload.event==='error'||payload.event==='crashed'){error=d.message;if(payload.event==='crashed')ready=false;}
     else if(payload.event==='narrator')log=[d,...log].slice(0,60);
   }).then(fn=>{if(disposed)fn();else{unlisten=fn;void load();}}).catch(e=>{error=String(e);});
   return ()=>{disposed=true;unlisten?.();};
 });
</script>

<div class="shell">
 <aside>
  <div class="brand"><img class="brand-logo" src={logo} alt=""/><strong>Narrator<span>Verse</span></strong></div>
  <nav aria-label="NarratorVerse">
   <button class:chosen={tab==='main'} on:click={()=>tab='main'}><Icon name="narrator" size={21}/>{t.main}</button>
   <button class:chosen={tab==='quick'} on:click={()=>tab='quick'}><Icon name="quick" size={21}/>{u.quick}</button>
   <button class:chosen={tab==='components'} on:click={()=>tab='components'}><Icon name="components" size={21}/>{t.components}</button>
  </nav>
 </aside>
 <main>
  <header class="page-title"><div><h1>{tab==='quick'?u.quick:tab==='components'?t.components:t.main}</h1><p class="hint page-description">{tab==='main'?'Napisy z gry czytane po polsku.':tab==='quick'?'Wklej tekst i posłuchaj.':'Modele i środowisko aplikacji.'}</p></div></header>
  {#if error}<div class="alert error" role="alert"><strong>{t.error}</strong><span>{error}</span><button aria-label={t.close} on:click={()=>error=''}><Icon name="close"/></button></div>{/if}
  {#if notice}<div class="alert" role="status"><Icon name="check"/><span>{notice}</span><button aria-label={t.close} on:click={()=>notice=''}><Icon name="close"/></button></div>{/if}
  {#if !ready}<section class="panel"><p>{u.backendDown}</p><button on:click={load}><Icon name="refresh"/>{t.refresh}</button></section>
  {:else if tab==='main'&&profile&&form}
   <section class="profile-bar" aria-label={t.profile}>
    <label>{t.profile}<select value={profiles?.selected||''} disabled={busy||quickBusy} on:change={e=>{const select=e.currentTarget;const id=select.value;select.value=profiles?.selected||'';void profileAction('profile_select',{id});}}>{#each profiles?.profiles||[] as p}<option value={p.id}>{p.name}</option>{/each}</select></label>
    <button disabled={busy||quickBusy} on:click={()=>{profileName='';profileDialog='create';}}><Icon name="plus"/>{t.new}</button>
    <button disabled={busy} on:click={()=>{profileName=profile?.name||'';profileDialog='rename';}}><Icon name="edit"/>{t.rename}</button>
    <button class="danger" disabled={busy||quickBusy||(profiles?.profiles.length||0)<=1} on:click={()=>confirm('Usunąć profil „'+profile?.name+'”?',()=>void profileAction('profile_delete'))}><Icon name="trash"/>{t.remove}</button>
   </section>
   {#if dirty}<div class="save-bar" role="region" aria-label="Zapis ustawień profilu"><span>{u.unsaved} · {profile.name}</span><button disabled={busy} on:click={discard}><Icon name="close"/>{u.discard}</button><button class="primary" disabled={active||busy} on:click={saveDraft}><Icon name="save"/>{u.saveChanges}</button></div>{/if}
   <section class="panel session-panel">
    <div class="section-heading"><h2>{t.session}</h2>{#if sessionState!=='empty'}<span class="badge" class:reading={sessionState==='reading'} role="status">{u[sessionState]||sessionState}</span>{/if}</div>
    {#if quickBusy}<div class="alert"><span>{u.quickConflict}</span><button on:click={()=>void action('quick_stop')}><Icon name="stop"/>{u.stopQuick}</button></div>{/if}
    <div class="transport"><button class="primary" disabled={busy||quickBusy||(dirty&&sessionState!=='reading')||(active&&!session?.has_frame&&sessionState!=='failed')} on:click={primary}><Icon name={sessionState==='reading'?'pause':!active||sessionState==='failed'?'monitor':!session?.has_frame?'refresh':!session.region_confirmed?'region':'play'}/>{sessionState==='reading'?t.pause:!active||sessionState==='failed'?u.chooseSource:!session?.has_frame?u.starting:!session.region_confirmed?u.confirmRegion:sessionState==='paused'?u.resume:t.read}</button>{#if active}<button disabled={busy} on:click={()=>void action('stop')}><Icon name="stop"/>{t.stop}</button>{/if}</div>
     {#if dirty}<p class="hint">Zapisz lub odrzuć zmiany profilu, zanim rozpoczniesz sesję.</p>{/if}
    {#if snap.message&&sessionState==='failed'}<p class="hint">{snap.message}</p>{/if}
   </section>
   <div class="narrator-grid">
    <section class="panel capture-panel"><h2>{t.source}</h2><p class="hint">{session?.has_frame?u.sourceSelected+': '+(session.source==='monitor'?t.monitor:t.window):u.sourceEmpty}</p>
     <div class="source-controls"><label>Rodzaj źródła<select value={draft.capture_source} disabled={locked||quickBusy} on:change={e=>edit('capture_source',e.currentTarget.value)}><option value="window">{t.window}</option><option value="monitor">{t.monitor}</option></select></label>{#if active}<button disabled={busy||quickBusy||dirty} on:click={()=>void action('change_source')}><Icon name="refresh"/>{t.change}</button>{/if}</div>
     <p class="hint">{t.sourceHint}</p>
     <div class="region-row"><strong>{t.region}</strong><button disabled={!session?.has_frame||busy||dirty} on:click={()=>void action('preview')}><Icon name="region"/>{u.selectRegion}</button></div>
     {#if editorImage&&session?.has_frame}<div class="region-thumbnail"><img src={editorImage} alt={t.region}/><div class="thumbnail-selection" style:left={`${profile.settings.subtitle_region.x*100}%`} style:top={`${profile.settings.subtitle_region.y*100}%`} style:width={`${profile.settings.subtitle_region.width*100}%`} style:height={`${profile.settings.subtitle_region.height*100}%`}></div></div><p class="hint">{session.region_confirmed?u.regionReady:u.selectSaved}</p>{:else}<div class="region-empty"><Icon name="region" size={34}/><p>{u.regionEmpty}</p></div>{/if}
    </section>
    <section class="panel voice-panel"><h2>Głos i czytanie</h2>
     <div class="voice-picker"><span class="field-label">{u.voice}</span><button class="voice-trigger" aria-expanded={voiceMenu} aria-controls="voice-options" disabled={busy} on:click={()=>voiceMenu=!voiceMenu}><Icon name="voice"/><strong>{voiceName}</strong><Icon name="chevron"/></button>
      {#if voiceMenu}<div id="voice-options" class="voice-options" role="group" aria-label="Wybór głosu">
       <button class:selected={!draft.voice_id||draft.voice_id==='voidek-pl-e991'} disabled={locked} on:click={()=>{edit('voice_id','voidek-pl-e991');voiceMenu=false;}}>Voidek{#if !draft.voice_id||draft.voice_id==='voidek-pl-e991'}<Icon name="check"/>{/if}</button>
       {#each (profiles?.voices||[]).filter(v=>v.voice_id!=='voidek-pl-e991') as v}<button class:selected={draft.voice_id===v.voice_id} disabled={locked||!v.installed} on:click={()=>{edit('voice_id',v.voice_id);voiceMenu=false;}}>{v.name}{v.installed?'':' · '+t.not_installed}{#if draft.voice_id===v.voice_id}<Icon name="check"/>{/if}</button>{/each}
       <button class="voice-import" disabled={locked||quickBusy||!!session?.component_job||session?.voice_job} on:click={()=>void action('voice_import')}><Icon name="upload"/>{u.importVoice}</button><p class="hint">{u.importHint}</p>
      </div>{/if}
     </div>
     <button disabled={busy||quickBusy||dirty||session?.reading||!!session?.component_job||session?.voice_job} on:click={()=>void action('voice_preview')}><Icon name="play"/>Posłuchaj zapisanego głosu</button>
     <div class="form-grid voice-sliders"><label>{t.rate}<output>{Number(draft.speech_rate||1).toFixed(2)}×</output><input type="range" min=".5" max="2" step=".05" value={draft.speech_rate} disabled={locked} on:input={e=>edit('speech_rate',Number(e.currentTarget.value))}/></label><label>{t.volume}<output>{Math.round((draft.volume??.85)*100)}%</output><input type="range" min="0" max="1" step=".05" value={draft.volume} disabled={locked} on:input={e=>edit('volume',Number(e.currentTarget.value))}/></label></div>
     <label class="check"><input type="checkbox" checked={draft.read_speaker_names} disabled={locked} on:change={e=>edit('read_speaker_names',e.currentTarget.checked)}/><span>{t.speaker}</span></label><p class="hint">{u.speakerHint}</p>
     <label class="check"><input type="checkbox" checked={draft.adaptive_speech_rate??true} disabled={locked} on:change={e=>edit('adaptive_speech_rate',e.currentTarget.checked)}/><span>{a.title}</span></label>
     <details><summary>Tempo i głos — szczegóły</summary><p class="hint">{a.hint}</p><div class="form-grid">{#each [['noise_scale','noise'],['noise_w_scale','noiseW']] as [key,label]}<label>{t[label]}<input type="number" min="0" max="2" step=".05" placeholder="Domyślne modelu" value={draft[key]??''} disabled={locked} on:input={e=>edit(key,e.currentTarget.value===''?null:Number(e.currentTarget.value))}/></label>{/each}</div>
      {#each (profiles?.voices||[]).filter(v=>v.voice_id.startsWith('custom-')) as v}<div class="region-row"><span>{v.name}</span><button class="danger" disabled={locked||quickBusy||!!session?.component_job} on:click={()=>confirm('Usunąć własny głos „'+v.name+'”?',()=>void action('voice_remove',{id:v.voice_id}))}><Icon name="trash"/>{t.remove}</button></div>{/each}
      <button disabled={locked} on:click={()=>void resetSection('voice')}><Icon name="reset"/>{t.reset}</button>
     </details>
    </section>
   </div>
   <section class="panel"><h2>{t.recognition}</h2><p class="hint">{u.recognitionHint}</p><div class="form-grid">
    <label>{t.engine}<select value={draft.ocr_provider_id} disabled={locked} on:change={e=>edit('ocr_provider_id',e.currentTarget.value)}><option value="">Tesseract · automatycznie</option><option value="tesseract-fast-eng">Tesseract</option><option value="rapidocr-local">RapidOCR</option></select></label>
    <label>{t.language}<select value={draft.subtitle_language_mode} disabled={locked} on:change={e=>edit('subtitle_language_mode',e.currentTarget.value)}><option value="english_to_polish">{t.english}</option><option value="polish">{t.polish}</option></select></label>
    {#if draft.subtitle_language_mode!=='polish'}<label>{t.translationProfile}<select value={draft.translation_profile_id} disabled={locked} on:change={e=>edit('translation_profile_id',e.currentTarget.value)}><option value="">{t.balanced} · automatycznie</option><option value="balanced">{t.balanced}</option><option value="fast">{t.fast}</option></select></label>{/if}
   </div><p class="hint">{draft.ocr_provider_id==='rapidocr-local'?t.rapidHint:u.modeHint}</p>
   <details><summary>{u.advanced}</summary>{#if draft.ocr_provider_id!=='rapidocr-local'}<label class="compact-field">{t.mode}<select value={form.ocrMode} disabled={locked} on:change={e=>{if(form)form=editOcr(form,e.currentTarget.value);}}><option value="automatic">{t.automatic}</option><option value="classic">{t.classic}</option></select></label>{/if}<div class="form-grid">{#each numberFields as [key,label,min,max,step]}<label>{t[label]}<input type="number" {min} {max} {step} value={draft[key]} disabled={locked} on:input={e=>edit(key,Number(e.currentTarget.value))}/></label>{/each}</div><button disabled={locked} on:click={()=>void resetSection('recognition')}><Icon name="reset"/>{t.reset}</button></details>
   </section>
   <section class="panel"><h2>{b.title}</h2><label class="check"><input type="checkbox" checked={draft.audio_balance_enabled??false} disabled={locked} on:change={e=>edit('audio_balance_enabled',e.currentTarget.checked)}/><span>{b.enabled}</span></label><p class="hint">{b.hint}</p>
    <div class="form-grid"><label>{b.application}<select value={draft.audio_balance_target||''} disabled={locked||audioLoading} on:change={e=>edit('audio_balance_target',e.currentTarget.value)}><option value="">{b.choose}</option>{#if draft.audio_balance_target&&!audioTargets.some(item=>item.target===draft.audio_balance_target)}<option value={draft.audio_balance_target}>{b.saved}</option>{/if}{#each audioTargets as item}<option value={item.target} disabled={item.ambiguous}>{item.label}{item.ambiguous?' · '+b.ambiguous:''}</option>{/each}</select></label><label>{b.depth}<select value={draft.audio_balance_db??-12} disabled={locked} on:change={e=>edit('audio_balance_db',Number(e.currentTarget.value))}><option value={-6}>{b.gentle}</option><option value={-12}>{b.balanced}</option><option value={-18}>{b.strong}</option></select></label></div>
    <button disabled={audioLoading||busy} on:click={()=>void refreshAudio()}><Icon name="refresh"/>{b.refresh}</button>
    {#if audioError}<p class="inline-error" role="alert">{b.loadError} · {audioError}</p>{:else if audioLoading}<p class="hint" role="status">{b.loading}</p>{:else if !audioLoaded}<p class="hint">{b.notLoaded}</p>{:else if !audioTargets.length}<p class="hint">{b.missing}</p>{/if}
    <label class="check"><input type="checkbox" checked={draft.normalize_narrator??false} disabled={locked} on:change={e=>edit('normalize_narrator',e.currentTarget.checked)}/><span>{b.normalize}</span></label><p class="hint">{b.normalizeHint}</p>
    {#if active&&draft.audio_balance_enabled}<p role="status">{b[snap.audio_balance?.state||'off']||snap.audio_balance?.state}{snap.audio_balance?.error?' · '+snap.audio_balance.error:''}</p>{/if}
    <details><summary>Jak działa balans?</summary><p class="hint">{b.baseline}</p><button disabled={locked} on:click={()=>void resetSection('audio')}><Icon name="reset"/>{t.reset}</button></details>
   </section>
   {#if active}<p class="hint">{u.stopToEdit}</p>{/if}
   <details class="panel diagnostics"><summary><Icon name="info"/>{t.diagnostics}</summary><div class="diagnostic-text"><div><strong>{t.text}</strong><p>{snap.last_detected_text||'—'}</p></div><div><strong>{t.translation}</strong><p>{snap.last_translation||'—'}</p></div></div><pre>{JSON.stringify(session,null,2)}</pre><details><summary>{t.paths}</summary><pre>{JSON.stringify(profiles?.paths,null,2)}</pre></details><pre>{log.map(e=>JSON.stringify(e)).join('\n')}</pre><button disabled={locked} on:click={()=>void resetSection('profile')}><Icon name="reset"/>{t.reset} · {t.profile}</button></details>
  {:else if tab==='quick'}
   <p class="hint">{u.quickHint}</p><section class="panel quick-panel">
    <label>{u.input}<textarea rows="7" maxlength="10000" value={quickText} on:input={e=>{quickText=e.currentTarget.value;localStorage.setItem('quick-text',quickText);}}></textarea></label><div class="text-count">{quickText.length.toLocaleString('pl-PL')} / 10 000</div>
    <div class="form-grid"><label>{u.voice}<select bind:value={quickOptions.voice_id} disabled={quickBusy||busy} on:change={saveQuick}>{#each profiles?.voices||[] as v}<option value={v.voice_id}>{v.name}{v.installed?'':' · '+t.not_installed}</option>{/each}</select></label><label>{t.rate} · {quickOptions.speech_rate.toFixed(2)}×<input type="range" min=".5" max="2" step=".05" bind:value={quickOptions.speech_rate} disabled={quickBusy||busy} on:change={saveQuick}/></label><label>{t.volume} · {Math.round(quickOptions.volume*100)}%<input type="range" min="0" max="1" step=".05" bind:value={quickOptions.volume} disabled={quickBusy||busy} on:change={saveQuick}/></label></div><p class="hint">{u.quickIndependent}</p>
    {#if session?.reading}<div class="alert"><span>{u.conflict}</span><button on:click={()=>void action('pause')}><Icon name="pause"/>{u.pauseLive}</button></div>{/if}
    {#if quick.error}<div class="alert error" role="alert"><span>{quick.error}</span>{#if quick.required_component}<button on:click={()=>tab='components'}>{t.components}</button>{/if}</div>{/if}
    <div class="transport"><button class="primary" disabled={quickBusy||busy||!quickText.trim()||session?.reading||!!session?.component_job} on:click={readQuick}><Icon name="play"/>{u.read}</button><button disabled={!quickBusy||quick.state==='stopping'} on:click={()=>void action('quick_stop')}><Icon name="stop"/>{u.stop}</button><button disabled={quickBusy} on:click={()=>{quickText='';localStorage.setItem('quick-text','');}}><Icon name="clear"/>{u.clear}</button></div>
    <p class="quick-status" role="status">{u[quick.state]||quick.state}{quickBusy&&quick.parts>1?' · '+quick.part+' / '+quick.parts:''}</p>
    <details><summary>{u.advanced}</summary><div class="button-row"><button disabled={active||busy||quickBusy||dirty} on:click={()=>confirm(u.applyProfile+'?',()=>void applyQuickToProfile())}><Icon name="arrow"/>{u.applyProfile}</button><button disabled={busy||quickBusy} on:click={()=>{quickOptions={voice_id:'voidek-pl-e991',speech_rate:1,volume:.85};void saveQuick();}}><Icon name="reset"/>{u.resetQuick}</button></div></details>
   </section>
  {:else if tab==='components'}
   <div class="section-heading"><p class="hint">{t.deleteHint}</p><button disabled={busy||session?.components_refreshing||!!session?.component_job} on:click={()=>void action('components_refresh',{},false)}><Icon name="refresh"/>{t.refresh}</button></div>
   {#if session?.components_refreshing}<p class="hint" role="status">{u.checking}</p>{/if}
   {#each components as c}<section class="panel component"><div class="section-heading"><h2>{c.name}</h2><span class="badge">{text(session?.component_job===c.component_id?'installing':c.state,t)}</span></div><p class="hint">{c.message}</p><small>{c.license_id} · {c.attribution}</small><div class="component-metadata"><span>{u[c.origin]||c.origin}</span>{#if c.version}<span>{c.version}</span>{/if}</div><div class="component-footer"><span>{c.installed_size_bytes!=null?u.installedSize+': '+(c.installed_size_bytes/1048576).toFixed(1)+' MiB':c.download_size_bytes!=null?u.downloadSize+': '+(c.download_size_bytes/1048576).toFixed(1)+' MiB':u.unknownSize}</span><div class="button-row"><button disabled={!c.installable||active||quickBusy||!!session?.component_job||session?.components_refreshing||busy} on:click={()=>void action('component',{component:c.component_id,action:c.managed?'repair':'install'})}><Icon name={c.managed?'refresh':'download'}/>{c.managed?t.repair:t.install}</button>{#if c.managed}<button disabled={active||quickBusy||!!session?.component_job||session?.components_refreshing||busy} on:click={()=>void action('component',{component:c.component_id,action:'verify'})}><Icon name="shield"/>{t.verify}</button><button class="danger" disabled={active||quickBusy||!!session?.component_job||session?.components_refreshing||busy} on:click={()=>confirm(t.deleteConfirm,()=>void action('component',{component:c.component_id,action:'remove'}))}><Icon name="trash"/>{t.remove}</button>{/if}</div></div>{#if session?.component_job===c.component_id}<div class="download"><progress max={download?.total||1} value={download?.bytes||0}></progress><span>{t.download}: {((download?.bytes||0)/1048576).toFixed(1)} MiB</span><button on:click={()=>void action('component_cancel',{},false)}>{t.cancel}</button></div>{/if}</section>{/each}
  {/if}
 </main>
</div>
{#if editor&&profile}<RegionEditor image={editorImage} initial={profile.settings.subtitle_region} saving={busy} save={saveRegion} close={()=>editor=false}/>{/if}
{#if profileDialog}<div class="modal-backdrop"><div class="modal small-modal" role="dialog" aria-modal="true" aria-label={profileDialog==='create'?t.new:t.rename} tabindex="-1"><form on:submit|preventDefault={submitProfile}><h2>{profileDialog==='create'?t.new:t.rename}</h2><p class="hint">{u.profileHint}</p><label>{t.name}<input bind:value={profileName} maxlength="100" required/></label><footer><button type="button" on:click={()=>profileDialog=''}>{t.cancel}</button><button class="primary" disabled={busy}><Icon name="save"/>{t.save}</button></footer></form></div></div>{/if}
{#if confirmAction}<div class="modal-backdrop"><div class="modal small-modal" role="dialog" aria-modal="true" aria-label={t.confirm} tabindex="-1"><h2>{t.confirm}</h2><p>{confirmText}</p><footer><button on:click={()=>confirmAction=null}>{t.cancel}</button><button class="primary" on:click={()=>{const fn=confirmAction;confirmAction=null;fn?.();}}><Icon name="check"/>{t.confirm}</button></footer></div></div>{/if}