import test from "node:test";
import assert from "node:assert/strict";
import { replyUtterance, readyVoices } from "./voice.js";
class Utterance { constructor(text) { this.text = text; } }
test("read aloud preserves the complete answer and selects a matching language voice", () => {
  const voices = [{ lang: "hi-IN" }, { lang: "en-US" }, { lang: "en-IN" }];
  const english = replyUtterance("First sentence.\nSecond sentence!", Utterance, voices);
  assert.equal(english.text, "First sentence.\nSecond sentence!");
  assert.equal(english.voice, voices[2]);
  const hindi = replyUtterance("नमस्ते, मैं आपकी मदद कर सकता हूँ।", Utterance, voices);
  assert.equal(hindi.lang, "hi-IN");
  assert.equal(hindi.voice, voices[0]);
});
test("read aloud falls back to a same-language voice or the browser default", () => {
  const voice = { lang: "en-GB" };
  assert.equal(replyUtterance("Hello", Utterance, [voice]).voice, voice);
  assert.equal(replyUtterance("Hello", Utterance).voice, null);
});


test("Indian English accent is preserved instead of switching to a US voice", () => {
  const basic = { name: "Microsoft Ravi", lang: "en-IN" };
  const natural = { name: "Microsoft Aria Online (Natural)", lang: "en-US" };
  const hindi = { name: "Natural Hindi", lang: "hi-IN" };
  const reply = replyUtterance("Hello, let us talk this through.", Utterance, [basic, hindi, natural]);
  assert.equal(reply.voice, basic);
  assert.equal(reply.lang, "en-IN");
  assert.equal(reply.volume, 0.7);
  assert.equal(reply.rate, 0.98);
  assert.equal(reply.pitch, 1);
});
test("late-loaded voices are used and their listener is released", async () => {
  const synthesis = new EventTarget();
  let voices = [];
  synthesis.getVoices = () => voices;
  const pending = readyVoices(synthesis);
  voices = [{ name: "Natural voice", lang: "en-IN" }];
  synthesis.dispatchEvent(new Event("voiceschanged"));
  assert.deepEqual(await pending, voices);
});
test("voice loading cannot block playback indefinitely", async () => {
  const synthesis = new EventTarget();
  synthesis.getVoices = () => [];
  assert.deepEqual(await readyVoices(synthesis, 5), []);
});


test("natural Indian English is preferred among voices with the intended accent", () => {
  const voices = [
    { name: "Microsoft Ravi", lang: "en-IN", default: true },
    { name: "Microsoft Aria Online (Natural)", lang: "en-US" },
    { name: "Microsoft Neerja Online (Natural)", lang: "en-IN" },
  ];
  assert.equal(replyUtterance("Let us discuss your options.", Utterance, voices).voice, voices[2]);
});
