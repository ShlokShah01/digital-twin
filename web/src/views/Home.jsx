import { useEffect, useState } from "react";
import { ArrowUpRight, ArrowRight, Brain, Graph as GraphIcon, ChatCircle, Files, CircleNotch } from "@phosphor-icons/react";
import { loadGraph } from "../api.js";
import { Button } from "../components/ui/button.jsx";
import { Textarea } from "../components/ui/textarea.jsx";

export default function Home({ health, profile, busy, notify }) {
  const [q, setQ] = useState("");
  const [optText, setOptText] = useState("");
  const [choices, setChoices] = useState(false);
  const [graph, setGraph] = useState(null);
  const [graphError, setGraphError] = useState("");
  useEffect(() => { loadGraph().then(setGraph).catch(e => setGraphError(e.message)); }, [profile]);
  const quickAsk = () => {
    if (!q.trim() || busy) return;
    sessionStorage.setItem("draft-question", q.trim());
    sessionStorage.setItem("draft-options", optText);
    notify("chat");
  };
  const chooseStarter = (text) => { setQ(text); document.getElementById("quick-q")?.focus(); };
  const topics = (profile?.topics || []).slice(0, 6);
  return <div className="overview">
    <header className="overview-heading"><div><h1>A clearer picture of you.</h1><p>Your words, patterns, and decisions. Connected in one place.</p></div><Button variant="outline" onClick={() => notify("chat")}><ChatCircle size={17} />Open chat<ArrowUpRight size={15} /></Button></header>
    <div className="overview-grid">
      <section className="ask-desk" aria-labelledby="ask-title">
        <div className="desk-symbol" aria-hidden="true"><Brain size={31} weight="duotone" /></div>
        <h2 id="ask-title">Think it through<br />with your twin.</h2>
        <p className="desk-intro">A second perspective, grounded in what makes you, you.</p>
        <div className="quick-composer">
          <label htmlFor="quick-q">What’s on your mind?</label>
          <Textarea id="quick-q" value={q} onChange={e => setQ(e.target.value)} rows={3} placeholder="A decision to make. A pattern to understand." onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); quickAsk(); } }} />
          {choices && <div className="quick-choices"><label htmlFor="quick-o">Choices to compare</label><Textarea id="quick-o" rows={3} value={optText} onChange={e=>setOptText(e.target.value)} placeholder="One choice per line" /></div>}
          <div className="composer-tools"><button type="button" onClick={() => setChoices(v => !v)} aria-expanded={choices}>{choices ? "Hide choices" : "+ Add choices"}</button><Button onClick={quickAsk} disabled={busy || !q.trim()}>Ask your twin<ArrowUpRight size={17} /></Button></div>
        </div>
        <div className="starter-list"><span>A place to start</span>{["What decision patterns do I repeat?", "How do I weigh money against convenience?", "What matters most when I choose a new project?"].map(text=><button key={text} type="button" onClick={()=>chooseStarter(text)}>{text}<ArrowUpRight size={15}/></button>)}</div>
      </section>
      <section className="identity-desk" aria-labelledby="identity-title">
        <div className="section-line"><h2 id="identity-title">Meet your twin</h2><a href="#/profile" aria-label="Open full profile"><ArrowUpRight size={19}/></a></div>
        <div className="identity-person"><span className="identity-avatar">{(profile?.name || "T").slice(0,1)}</span><div><h3>{profile?.name || "Your twin"}</h3><span>{profile ? "Learned from your writing" : health && !health.twin_built ? "Build your twin to see its profile" : "Loading your profile…"}</span></div></div>
        <p className="identity-persona">{profile?.persona || "Your twin’s profile appears here once it has learned from your source files."}</p>
        {topics.length > 0 && <div className="topic-field"><h3>Recurring topics</h3><div>{topics.map(([topic])=><span key={topic}>{topic}</span>)}</div></div>}
        <div className="identity-counts"><div><Files size={18}/><span>Source documents</span><b>{profile?.stats?.n_documents ?? "—"}</b></div><div><Brain size={18}/><span>Evidence chunks</span><b>{health?.chunks ?? "—"}</b></div><div><GraphIcon size={18}/><span>Knowledge connections</span><b>{graph?.stats?.edges ?? "—"}</b></div></div>
        <a className="text-link" href="#/profile">Explore the full profile<ArrowRight size={16}/></a>
      </section>
      <section className="patterns-desk" aria-labelledby="patterns-title"><div className="section-line"><h2 id="patterns-title">How you tend to decide</h2><a href="#/profile">View profile<ArrowUpRight size={14}/></a></div>{profile?.decision_patterns?.length ? <div className="pattern-rows">{profile.decision_patterns.slice(0,3).map((p,i)=><div key={i}><h3>{p.name}</h3><p>{p.behavior}</p></div>)}</div> : <p className="text-muted">Decision patterns appear when your sources contain enough evidence.</p>}</section>
      <section className="knowledge-desk" aria-labelledby="knowledge-title"><div className="section-line"><h2 id="knowledge-title">Your connected knowledge</h2><a href="#/graph" aria-label="Explore knowledge graph"><ArrowUpRight size={19}/></a></div>
        <div className="knowledge-preview">{graph?.clusters?.length ? <svg viewBox="0 0 400 150" role="img" aria-label="Preview of knowledge communities"><g stroke="var(--border-strong)" strokeWidth="1">{graph.clusters.slice(0,7).map((c,i)=><path key={c.id} d={`M200 75 Q${80+i*40} 25 ${45+i*48} ${i%2 ? 115 : 35}`} fill="none"/>)}</g>{graph.clusters.slice(0,7).map((c,i)=><g key={c.id}><circle cx={45+i*48} cy={i%2 ? 115 : 35} r={Math.min(17,7+c.size)} fill={i%2 ? "var(--accent)" : "var(--muted)"} opacity=".8"/><text x={45+i*48} y={i%2 ? 143 : 11} textAnchor="middle" fill="var(--muted)" fontSize="10">{c.label?.[0]?.slice(0,12) || "community"}</text></g>)}<circle cx="200" cy="75" r="19" fill="var(--surface-3)" stroke="var(--accent)"/><text x="200" y="79" textAnchor="middle" fill="var(--foreground)" fontSize="11">Twin</text></svg> : <p>{graphError ? "Graph unavailable. Open the graph to retry." : graph ? "Build your twin to connect its knowledge." : "Loading connections…"}</p>}</div>
        <a className="text-link" href="#/graph">{graph?.stats?.communities ?? "—"} communities · Explore the graph<ArrowRight size={16}/></a>
      </section>
    </div>
    <div className="runtime-strip"><span><span className={health?.twin_built ? "status-dot" : "status-dot waiting"}/> {health ? health.twin_built ? "Twin ready" : "Build needed" : "Connecting…"}</span><span>Laya · {health?.laya_enabled === false ? "disabled" : health?.laya_device?.startsWith("cuda") ? health.laya_loaded ? "GPU ready" : "GPU configured" : "device pending"}</span><span>Narrator · {health?.llm ? health.llm_model?.split("/").pop() || "enabled" : health ? "offline" : "connecting"}</span></div>
  </div>;
}
