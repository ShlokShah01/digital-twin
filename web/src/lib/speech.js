export async function speechAudio(text, voice, signal) {
  const response = await fetch("/api/speech", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }), signal,
  });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch {}
    throw new Error(typeof detail === "string" ? detail : "Speech could not be generated. Please try again.");
  }
  if (!response.headers.get("Content-Type")?.startsWith("audio/wav")) throw new Error("No playable audio was returned.");
  return response.blob();
}
