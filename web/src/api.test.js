import test from 'node:test';
import assert from 'node:assert/strict';
import { answerPreview, askStream } from './api.js';
test('partial answer handles split Unicode and escaped quotes', () => {
  const answer = 'hello "friend"\nnext';
  const raw = JSON.stringify({answer, reasoning:'evidence'});
  for(let n=0;n<=raw.length;n++) assert.ok(answer.startsWith(answerPreview(raw.slice(0,n))));
  assert.equal(answerPreview(raw),answer);
  assert.equal(answerPreview('{"answer":"hi\\u09'), 'hi');
});
test('stream survives fragmented chunks and requires final answer', async () => {
  const original = globalThis.fetch;
  const events = [{type:'text',data:'{"answer":"hello"}'},{type:'answer',data:{answer:'hello'}}];
  const bytes = new TextEncoder().encode(events.map(e=>JSON.stringify(e)).join('\n'));
  globalThis.fetch = async () => new Response(new ReadableStream({start(c) {
    for(let n=0;n<bytes.length;n+=5)c.enqueue(bytes.slice(n,n+5)); c.close();
  }}));
  try {
    const previews=[];
    assert.deepEqual(await askStream('hello',[],p=>previews.push(p)),{answer:'hello'});
    assert.deepEqual(previews,['hello']);
    globalThis.fetch = async () => new Response('{"type":"text","data":""}\n');
    await assert.rejects(askStream('hello',[],()=>{}),/before the answer completed/);
    globalThis.fetch = async () => new Response('{"type":"error","data":"unavailable"}\n');
    await assert.rejects(askStream('hello',[],()=>{}),/unavailable/);
  } finally {globalThis.fetch=original;}
});

import { voiceDraft } from './lib/voice.js';
test('dictation preserves draft and replaces interim text without duplicates', () => {
  assert.equal(voiceDraft('My question ', [[{transcript:'first'}]]), 'My question first');
  assert.equal(voiceDraft('My question ', [[{transcript:'first final'}],[{transcript:'second'}]]), 'My question first final second');
  assert.equal(voiceDraft('', []), '');
});

test('older backend falls back to the existing ask route on 404', async () => {
  const original=globalThis.fetch; const paths=[];
  globalThis.fetch=async path=> { paths.push(path); return path.endsWith('/stream')
    ? new Response('{"detail":"Not Found"}', {status:404})
    : new Response('{"answer":"Hello!"}',{status:200}); };
  try {
    assert.deepEqual(await askStream('hello',[],()=>{}),{answer:'Hello!'});
    assert.deepEqual(paths,['/api/ask/stream','/api/ask']);
  } finally {globalThis.fetch=original;}
});
