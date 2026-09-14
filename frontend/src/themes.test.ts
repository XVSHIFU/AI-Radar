import assert from "node:assert/strict";
import test from "node:test";
import {themes,resolveTheme,mix} from "./themes";
const lum=(hex:string)=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]!*.2126+c[1]!*.7152+c[2]!*.0722};
const ratio=(a:string,b:string)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
test("each theme preserves readable roles on its actual page surfaces",()=>{
assert.equal(themes.length,16);assert.equal(new Set(themes.map(t=>t.id)).size,16);
for(const t of themes){const c=t.colors;
for(const bg of ["bg","paper","rail"])for(const fg of ["ink","muted","blue"])assert.ok(ratio(c[fg]!,c[bg]!)>=4.5,t.name+" "+fg+"/"+bg+" "+ratio(c[fg]!,c[bg]!));
for(const [fg,bg] of [["pill-ink","aqua"],["conversation-assistant","conversation-complete-bg"],["conversation-demo","conversation-partial-bg"],["demo-ink","demo-bg"]])assert.ok(ratio(c[fg!]!,c[bg!]!)>=4.5,t.name+" "+fg+"/"+bg);
assert.ok(ratio("#ffffff",c.blue!)>=4.5,t.name+" primary");
assert.ok(ratio(c.focus!,c.paper!)>=3,t.name+" focus");
}});
test("invalid or removed stored themes recover to a complete safe default",()=>{
assert.equal(resolveTheme(null).id,"mist");assert.equal(resolveTheme("unknown").id,"mist");
assert.equal(resolveTheme("paper").name,"暖纸松绿");assert.equal(mix("#ffffff","#000000",0),"#ffffff");
for(const t of themes)for(const value of Object.values(t.colors))assert.match(value,/^#[0-9a-f]{6}$/i);
});
