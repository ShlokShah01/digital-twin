// Results include prior final segments plus the latest interim segment.
export function voiceDraft(original, results) {
  const transcript = Array.from(results).map(result => result[0].transcript).join(" ");
  return [original.trimEnd(), transcript].filter(Boolean).join(" ");
}


export function replyUtterance(text, Utterance, voices = []) {
  const utterance = new Utterance(text);
  utterance.lang = /[\u0900-\u097f]/.test(text) ? "hi-IN" : "en-IN";
  const language = utterance.lang.slice(0, 2);
  utterance.voice = voices.find(voice => voice.lang === utterance.lang)
    || voices.find(voice => voice.lang.toLowerCase().startsWith(language)) || null;
  utterance.rate = 1;
  return utterance;
}
