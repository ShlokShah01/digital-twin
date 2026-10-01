import { useState } from "react";
import { Button } from "../components/ui/button.jsx";
import { Palette, Bell, Timer, Graph, ArrowUpRight } from "@phosphor-icons/react";
const THEMES = [
  { id: "ivory", name: "Warm Ivory", note: "Cream, bronze, and editorial warmth", colors: ["#faf8f4", "#f0ede6", "#7b684e"] },
  { id: "slate", name: "Cool Slate", note: "Clean whites and quiet blue accents", colors: ["#fcfdfe", "#edf1f6", "#46678b"] },
  { id: "sage", name: "Soft Sage", note: "Gentle greens and a calm workspace", colors: ["#fcfcf9", "#eff3ed", "#4c6956"] },
  { id: "dark", name: "Evening", note: "A softer dark theme for low light", colors: ["#191b1c", "#252829", "#d6bb8b"] },
];
function Toggle({ title, help, checked, onChange, disabled = false }) {
  return <label className="setting-row"><span><strong>{title}</strong><small>{help}</small></span><input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} /></label>;
}
export default function Settings({ preferences: p, onChange, health }) {
  const [notice, setNotice] = useState("");
  const [requesting, setRequesting] = useState(false);
  const supportsNotifications = typeof Notification !== "undefined";
  const update = patch => onChange({ ...p, ...patch });
  const notifications = async () => {
    if (p.notifications) { update({ notifications: false }); return; }
    setRequesting(true);
    try {
      const permission = await Notification.requestPermission();
      update({ notifications: permission === "granted" });
      setNotice(permission === "granted" ? "Reply notifications are enabled." : "Notifications are blocked. You can allow them in your browser's site settings.");
    } catch { setNotice("This browser could not enable notifications."); }
    finally { setRequesting(false); }
  };
  return <div className="settings-page">
    <header><h1>Settings</h1><p>Make this workspace feel like yours. Changes save automatically in this browser.</p></header>
    <section aria-labelledby="appearance-title"><h2 id="appearance-title"><Palette size={20} />Appearance</h2><p>Choose a theme for the whole workspace.</p>
      <div className="theme-options">{THEMES.map(theme => <button type="button" key={theme.id} aria-pressed={p.theme === theme.id} onClick={() => update({ theme: theme.id })} className="theme-option">
        <span className="theme-sample" aria-hidden="true">{theme.colors.map(color => <span key={color} style={{ background: color }} />)}</span><strong>{theme.name}</strong><small>{theme.note}</small><span className="theme-selected">{p.theme === theme.id ? "Selected" : "Use theme"}</span>
      </button>)}</div>
      <label className="setting-row"><span><strong>Chat text size</strong><small>A comfortable reading size for messages and replies.</small></span><select value={p.textSize} onChange={e => update({ textSize: e.target.value })}><option value="standard">Standard</option><option value="large">Larger</option></select></label>
      <Toggle title="Interface motion" help="Allow subtle transitions. Your system's reduced-motion preference is always respected." checked={p.motion} onChange={() => update({ motion: !p.motion })} />
    </section>
    <section aria-labelledby="chat-settings-title"><h2 id="chat-settings-title"><Timer size={20} />Chat and notifications</h2>
      <label className="setting-row"><span><strong>Read-aloud voice</strong><small>Pocket TTS generates English speech locally on the backend CPU. Choose the voice you prefer.</small></span><select value={p.speechVoice || "alba"} onChange={e => update({ speechVoice: e.target.value })}><option value="alba">Alba · conversational</option><option value="marius">Marius</option><option value="anna">Anna</option></select></label>
      <Toggle title="Show response time" help="Show measured completion time below replies. Hidden by default to keep chat clean." checked={p.timings} onChange={() => update({ timings: !p.timings })} />
      <Toggle title="Reply notifications" help={supportsNotifications ? "Notify when an answer finishes while this tab is in the background. Reply content stays private." : "Desktop notifications are not supported in this browser."} checked={p.notifications} onChange={notifications} disabled={!supportsNotifications || requesting} />
      {supportsNotifications && Notification.permission === "denied" && <p className="setting-note">Your browser currently blocks notifications for this site.</p>}
      {notice && <p role="status" className="setting-note">{notice}</p>}
    </section>
    <section aria-labelledby="graph-settings-title"><h2 id="graph-settings-title"><Graph size={20} />Knowledge graph</h2><label className="setting-row"><span><strong>Community colors</strong><small>Change the graph's colors without changing its data or relationships.</small></span><select value={p.graphPalette} onChange={e => update({ graphPalette: e.target.value })}><option value="theme">Follow workspace theme</option><option value="warm">Warm earth</option><option value="cool">Cool blues</option><option value="sage">Forest greens</option></select></label><a className="settings-link" href="#/graph">Open knowledge graph<ArrowUpRight size={16} /></a></section>
    <section aria-labelledby="resources-title"><h2 id="resources-title">Resources and system</h2><p>Useful pages and the backend's current reported status.</p><div className="settings-resources"><a href="#/resources">Guides and resources<ArrowUpRight size={16} /></a><a href="#/how">How it works<ArrowUpRight size={16} /></a><a href="#/profile">Your twin profile<ArrowUpRight size={16} /></a><a href="#/home">Workspace overview<ArrowUpRight size={16} /></a></div>
      <dl className="settings-runtime"><div><dt>Answer model</dt><dd>{health?.llm_model || "Unavailable"}</dd></div><div><dt>Laya device</dt><dd>{health?.laya_loaded ? String(health.laya_device).toUpperCase() : "Not loaded"}</dd></div><div><dt>Knowledge index</dt><dd>{health ? `${health.chunks ?? 0} chunks` : "Unavailable"}</dd></div></dl>
    </section><Button variant="outline" onClick={() => { onChange({ speechVoice: "alba", theme: "ivory", textSize: "standard", graphPalette: "theme", timings: false, notifications: false, motion: true }); setNotice("Workspace preferences reset. Your conversations are preserved."); }}>Reset workspace preferences</Button>
  </div>;
}
