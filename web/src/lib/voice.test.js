import test from "node:test";
import assert from "node:assert/strict";
import { speechAudio } from "./speech.js";
test("Pocket audio sends only the requested answer and voice to the local endpoint", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/speech");
    assert.deepEqual(JSON.parse(options.body), { text: "Hello!", voice: "alba" });
    assert.equal(options.signal, controller.signal);
    return new Response(new Uint8Array([82, 73, 70, 70]), { headers: { "Content-Type": "audio/wav" } });
  };
  try { assert.equal((await speechAudio("Hello!", "alba", controller.signal)).size, 4); }
  finally { globalThis.fetch = original; }
});
test("speech errors remain visible and non-audio responses are rejected", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('{"detail":"Speech is busy"}', { status: 429 });
    await assert.rejects(speechAudio("Hello", "alba"), /Speech is busy/);
    globalThis.fetch = async () => new Response("bad", { headers: { "Content-Type": "text/plain" } });
    await assert.rejects(speechAudio("Hello", "alba"), /No playable audio/);
  } finally { globalThis.fetch = original; }
});
