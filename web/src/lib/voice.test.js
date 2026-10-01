import test from "node:test";
import assert from "node:assert/strict";
import { replyUtterance } from "./voice.js";
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
