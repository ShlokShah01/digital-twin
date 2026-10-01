export const THEMES = ["ivory", "slate", "sage", "dark"];
export const DEFAULTS = { theme: "ivory", textSize: "standard", graphPalette: "theme", timings: false, notifications: false, motion: true };
export function normalizePreferences(raw) {
  const value = raw && typeof raw === "object" ? raw : {};
  return { theme: THEMES.includes(value.theme) ? value.theme : DEFAULTS.theme,
    textSize: ["standard", "large"].includes(value.textSize) ? value.textSize : DEFAULTS.textSize,
    graphPalette: ["theme", "warm", "cool", "sage"].includes(value.graphPalette) ? value.graphPalette : DEFAULTS.graphPalette,
    timings: value.timings === true, notifications: value.notifications === true, motion: value.motion !== false };
}
export function loadPreferences() {
  try { return normalizePreferences(JSON.parse(localStorage.getItem("digital-twin.preferences"))); }
  catch { return { ...DEFAULTS }; }
}
