import test from "node:test";
import assert from "node:assert/strict";
import { normalizePreferences, DEFAULTS } from "./preferences.js";
test("preferences reject invalid themes and preserve independent options", () => {
  assert.deepEqual(normalizePreferences(null), DEFAULTS);
  assert.deepEqual(normalizePreferences({ theme: "unknown", notifications: "yes", timings: true, graphPalette: "cool", textSize: "large", motion: false }), { ...DEFAULTS, timings: true, graphPalette: "cool", textSize: "large", motion: false });
  assert.equal(normalizePreferences({ theme: "dark" }).theme, "dark");
});
