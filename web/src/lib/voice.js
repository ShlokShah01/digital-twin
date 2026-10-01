// Results include prior final segments plus the latest interim segment.
export function voiceDraft(original, results) {
  const transcript = Array.from(results).map(result => result[0].transcript).join(" ");
  return [original.trimEnd(), transcript].filter(Boolean).join(" ");
}
