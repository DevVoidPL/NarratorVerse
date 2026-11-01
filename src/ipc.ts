import { invoke } from '@tauri-apps/api/core';
export type Settings = Record<string, any>;
export type Rect = {x:number; y:number; width:number; height:number};
export type Profile = {id:string; name:string; settings:Settings; ocr:{mode:string}};
export type Voice = {voice_id:string; name:string; installed:boolean};
export type Profiles = {selected:string; profiles:Profile[]; voices:Voice[]; paths:Record<string,string>};
export type Component = {component_id:string; name:string; state:string; download_size_bytes:number|null; installed_size_bytes:number|null; attribution:string; license_id:string; message:string; managed:boolean; installable:boolean; origin:string; version:string; verified:boolean; installed:boolean};
export function rpc<T=any>(method:string, params:Record<string,unknown>={}):Promise<T> {
    return invoke<T>('rpc', {method,params});
}