export function matchesConversation(session, query) {
  const needle = query.trim().toLocaleLowerCase();
  return !needle || [session.title || "", ...(session.messages || []).flatMap(m => [m.question || "", m.answer?.answer || ""])].some(text => text.toLocaleLowerCase().includes(needle));
}

export function conversationMarkdown(session) {
  const title = (session.title || "Conversation").replace(/[\r\n]+/g, " ");
  const turns = (session.messages || []).map(message => {
    if (message.role === "user") {
      const choices = message.options?.length ? "\n\nChoices:\n" + message.options.map(option => "- " + option).join("\n") : "";
      return "## You\n\n" + (message.question || "") + choices;
    }
    if (message.thinking || message.error || !message.answer?.answer) return "";
    return "## Digital Twin\n\n" + message.answer.answer;
  }).filter(Boolean);
  return "# " + title + "\n\n" + turns.join("\n\n") + "\n";
}

export function downloadConversation(session) {
  const url = URL.createObjectURL(new Blob([conversationMarkdown(session)], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = (session.title || "conversation").replace(/[^a-z0-9_-]+/gi, "-").slice(0, 64) + ".md";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
