import type {Profile} from './ipc';

export type Draft = {
 profileId:string;
 values:Record<string,any>;
 ocrMode:string;
 edited:string[];
 ocrEdited:boolean;
};

export function createDraft(profile:Profile):Draft {
 return {profileId:profile.id,values:{...profile.settings},ocrMode:profile.ocr.mode,edited:[],ocrEdited:false};
}
export function isDirty(draft:Draft):boolean {return !!draft.edited.length||draft.ocrEdited;}
export function receiveProfile(draft:Draft|null,profile:Profile):Draft {
 return draft?.profileId===profile.id&&isDirty(draft)?draft:createDraft(profile);
}
export function editDraft(draft:Draft,key:string,value:unknown):Draft {
 return {...draft,values:{...draft.values,[key]:value},edited:[...new Set([...draft.edited,key])]};
}
export function editOcr(draft:Draft,mode:string):Draft {return {...draft,ocrMode:mode,ocrEdited:true};}
export function savePayload(draft:Draft) {
 return {values:Object.fromEntries(draft.edited.map(key=>[key,draft.values[key]])),
   ...(draft.ocrEdited?{ocr_mode:draft.ocrMode}:{})};
}
export function savedMatches(draft:Draft,profile:Profile):boolean {
 return draft.profileId===profile.id&&draft.edited.every(key=>
   JSON.stringify(draft.values[key])===JSON.stringify(profile.settings[key]))&&
   (!draft.ocrEdited||draft.ocrMode===profile.ocr.mode);
}