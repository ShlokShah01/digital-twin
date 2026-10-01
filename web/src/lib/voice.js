// Results include prior final segments plus the latest interim segment.
export function voiceDraft(original, results) {
  const transcript = Array.from(results).map(result => result[0].transcript).join(" ");
  return [original.trimEnd(), transcript].filter(Boolean).join(" ");
}


export function replyUtterance(text, Utterance, voices = []) {
  const utterance = new Utterance(text);
  utterance.lang = /[\u0900-\u097f]/.test(text) ? "hi-IN" : "en-IN";
  const language = utterance.lang.slice(0, 2);
  const score = voice => {
    const name = voice.name || "";
    const quality = /natural|neural|premium|enhanced/i.test(name) ? 100 : /google|online/i.test(name) ? 60 : 0;
    // Preserve the intended accent before comparing voice quality.
    return quality + (voice.lang.toLowerCase() === utterance.lang.toLowerCase() ? 200 : 0) + (voice.default ? 1 : 0);
  };
  utterance.voice = voices.filter(voice => voice.lang.toLowerCase().startsWith(language))
    .sort((a, b) => score(b) - score(a))[0] || null;
  if (utterance.voice) utterance.lang = utterance.voice.lang;
  utterance.rate = 0.98;
  utterance.pitch = 1;
  utterance.volume = 0.7;
  return utterance;
}

export function readyVoices(synthesis, timeout = 700) {
  const voices = synthesis.getVoices();
  if (voices.length) return Promise.resolve(voices);
  return new Promise(resolve => {
    const finish = () => {
      clearTimeout(timer);
      synthesis.removeEventListener("voiceschanged", changed);
      resolve(synthesis.getVoices());
    };
    const changed = () => { if (synthesis.getVoices().length) finish(); };
    const timer = setTimeout(finish, timeout);
    synthesis.addEventListener("voiceschanged", changed);
    changed();
  });
}
