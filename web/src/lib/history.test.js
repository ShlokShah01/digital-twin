import test from "node:test";
import assert from "node:assert/strict";
import { matchesConversation, conversationMarkdown, downloadConversation } from "./history.js";
test("search finds titles, questions and answers without searching hidden metadata", () => {
  const session = { title: "Plans", messages: [{ question: "Trip to Mumbai?", answer: { answer: "Take the train", reasoning: "private evidence" } }] };
  for (const query of [" plans ", "MUMBAI", "train", ""]) assert.equal(matchesConversation(session, query), true);
  assert.equal(matchesConversation(session, "private evidence"), false);
});
test("export includes readable turns and choices while omitting metadata, errors and unfinished answers", () => {
  const session = { title: "My\nchat", messages: [
    { role: "user", question: "नमस्ते", options: ["A", "B"] },
    { role: "assistant", answer: { answer: "Hello!", reasoning: "hidden" } },
    { role: "assistant", thinking: true, preview: "unfinished" },
    { role: "assistant", error: "server detail" },
  ] };
  assert.equal(conversationMarkdown(session), "# My chat\n\n## You\n\nनमस्ते\n\nChoices:\n- A\n- B\n\n## Digital Twin\n\nHello!\n");
});

test("download creates a Markdown attachment and releases its temporary URL", async t => {
  const events = [];
  const link = { click: () => events.push("click"), remove: () => events.push("remove") };
  t.mock.method(URL, "createObjectURL", blob => { assert.equal(blob.type, "text/markdown;charset=utf-8"); return "blob:test"; });
  t.mock.method(URL, "revokeObjectURL", url => events.push(url));
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const oldDocument = globalThis.document;
  globalThis.document = { createElement: tag => { assert.equal(tag, "a"); return link; }, body: { append: element => assert.equal(element, link) } };
  try {
    downloadConversation({ title: "A/B", messages: [] });
    assert.equal(link.download, "A-B.md");
    assert.equal(link.href, "blob:test");
    assert.deepEqual(events, ["click", "remove"]);
    t.mock.timers.tick(1000);
    assert.deepEqual(events, ["click", "remove", "blob:test"]);
  } finally { if (oldDocument === undefined) delete globalThis.document; else globalThis.document = oldDocument; }
});
