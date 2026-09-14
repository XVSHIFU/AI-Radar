import assert from "node:assert/strict";
import test from "node:test";
import { boundedHistory, restoreConversations } from "./conversation-store.js";
const base = { createdAt: 1, scope: "全部", mode: "live" as const };
test("restoring marks unfinished requests interrupted without changing completed turns", () => {
 const [row] = restoreConversations([{ id:"c", title:"t", draft:"", createdAt:1, updatedAt:1, messages:[{...base,id:"u",role:"user",text:"q"},{...base,id:"a",role:"assistant",text:"",status:"running"},{...base,id:"done",role:"assistant",text:"ok",status:"completed"}] }]);
 assert.equal(row.messages[1].status, "interrupted"); assert.equal(row.messages[2].status, "completed");
});
test("bounded history only includes finished paired turns and stays within API limits", () => {
 const messages = [{...base,id:"u1",role:"user" as const,text:"a".repeat(4001)},{...base,id:"a1",role:"assistant" as const,text:"b".repeat(4001),status:"completed" as const},{...base,id:"u2",role:"user" as const,text:"bad"},{...base,id:"a2",role:"assistant" as const,text:"",status:"error" as const},{...base,id:"u3",role:"user" as const,text:"new"}];
 const history = boundedHistory(messages, "u3"); assert.equal(history.length, 2); assert.ok(history.every((x) => x.content.length <= 4000)); assert.ok(history.reduce((n,x)=>n+x.content.length,0) <= 12000);
});
