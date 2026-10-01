export async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

export function loadHealth() {
  return api("/api/health");
}

export function loadProfile() {
  return api("/api/profile");
}

export function loadGraph() {
  return api("/api/graph");
}

export function ask(question, options) {
  return api("/api/ask", { method: "POST", body: JSON.stringify({ question, options }) });
}

export function rebuild() {
  return api("/api/build", { method: "POST", body: JSON.stringify({ no_llm: true }) });
}

export function splitOptions(raw) {
  return String(raw || "")
    .split(/[\n;|]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function pct(x) {
  x = Number(x);
  return Number.isFinite(x) ? Math.round(x * 1000) / 10 + "%" : "0%";
}

export function chunkText(s, n = 160) {
  s = String(s ?? "");
  return s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
}

export const PALETTE = [
  "var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)",
];

// Decode only a complete prefix of the answer string, including split escapes.
export function answerPreview(raw) {
  const match = /"answer"\s*:\s*"((?:[^"\\]|\\.)*)/.exec(raw);
  if (!match) return "";
  let value = match[1];
  while (value) {
    try { return JSON.parse('"' + value + '"'); }
    catch { value = value.slice(0, -1); }
  }
  return "";
}

export async function askStream(question, options, onPreview) {
  const res = await fetch("/api/ask/stream", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({question, options}),
  });
  // An older running server can serve the new bundle without the stream route.
  if (res.status === 404 || res.status === 405) return ask(question, options);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || res.statusText);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", answer;
  function consume(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "error") throw new Error(event.data);
    if (event.type === "text") onPreview(answerPreview(event.data));
    if (event.type === "answer") answer = event.data;
  }
  try {
    while (true) {
      const {done, value} = await reader.read();
      buffer += decoder.decode(value, {stream: !done});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach(consume);
      if (done) break;
    }
    consume(buffer);
    if (!answer) throw new Error("Connection ended before the answer completed. Please retry.");
    return answer;
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
