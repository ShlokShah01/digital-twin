import { useEffect, useMemo, useState } from "react";
import { loadGraph, PALETTE } from "../api.js";
import { Card, CardContent } from "../components/ui/card.jsx";
import { Skeleton } from "../components/ui/skeleton.jsx";

const W = 820;
const H = 560;

function layout(clusters) {
  const N = Math.min(clusters.length, 14);
  const cx = W / 2;
  const cy = H / 2;
  const rx = N <= 1 ? 0 : W / 2 - 75;
  const ry = N <= 1 ? 0 : H / 2 - 75;
  return clusters.slice(0, N).map((_, i) => {
    const a = (i / N) * Math.PI * 2 - Math.PI / 2;
    return { x: cx + Math.cos(a) * rx, y: cy + Math.sin(a) * ry };
  });
}

function GraphCard({ g, sel, setSel }) {
  const { arcs, dots } = useMemo(() => {
    if (!g) return { arcs: null, dots: null };
    const all = g.clusters || [];
    const clusters = all.slice(0, Math.min(all.length, 14));
    const pos = layout(clusters);
    const rFor = (c) => Math.max(14, Math.min(46, 8 + c.size * 2.4));
    const maxW = Math.max(1, ...g.comm_links.map((l) => l.weight));
    const links = g.comm_links.map((l) => {
      const a = pos[l.source];
      const b = pos[l.target];
      if (!a || !b) return null;
      const mx = (a.x + b.x) / 2 + (H / 2 - (a.y + b.y) / 2) * 0.16;
      const my = (a.y + b.y) / 2 - (W / 2 - (a.x + b.x) / 2) * 0.16;
      return { key: l.source + "-" + l.target, d: `M${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`, w: l.weight, maxW };
    }).filter(Boolean);
    const big = Math.max(0, ...clusters.map((c) => c.size));
    const arcs = links.map((l) => (
      <path key={l.key} d={l.d} style={{ stroke: "var(--color-border-strong)" }} strokeWidth={0.6 + 2.4 * (l.w / l.maxW)} opacity={0.25 + 0.45 * (l.w / l.maxW)} fill="none" />
    ));
    const dots = clusters.map((c, i) => {
      const p = pos[i];
      const heavy = c.size >= big * 0.5;
      return (
        <g key={c.id} data-i={i} role="button" tabIndex={0} aria-label={`Highlight community ${c.label?.[0] || c.id}`} aria-pressed={sel === i} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSel(s => s === i ? null : i); } }} onClick={() => setSel((s) => (s === i ? null : i))} className="cursor-pointer">
          <title>{[c.label, c.size + " members"].filter(Boolean).join(" \u00b7 ")}</title>
          <circle cx={p.x} cy={p.y} r={rFor(c)} fill={PALETTE[i % PALETTE.length]} opacity={sel == null || sel === i ? 1 : 0.14} />
          <text x={p.x} y={p.y + 4} textAnchor="middle" fill="var(--graph-label)" fontSize={13} fontWeight={700}>
            {c.size}
          </text>
          {(heavy || clusters.length <= 8) && c.label?.[0] && (
            <text x={p.x} y={p.y - rFor(c) - 6} textAnchor="middle" style={{ fill: "var(--color-foreground)" }} fontSize={11}>
              {c.label[0]}
            </text>
          )}
        </g>
      );
    });
    return { arcs, dots };
  }, [g, sel]);

  if (!g) return null;

  const legend = g.clusters.map((c, i) => (
    <button
      key={c.id}
      type="button"
      onClick={() => setSel((x) => (x === i ? null : i))}
      className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-surface-2"
      aria-pressed={sel === i}
    >
      <span className="size-2.5 shrink-0 rounded-full" style={{ background: PALETTE[i % PALETTE.length], opacity: sel == null || sel === i ? 1 : 0.25 }} />
      <span className="min-w-0 flex-1 truncate text-[12.5px]">
        {c.id} {"\u00b7"} {c.label.slice(0, 3).join(", ") || "keyword cluster"}
      </span>
      <span className="font-mono text-[11px] text-subtl">{c.size}</span>
    </button>
  ));

  const selDetails = sel != null && g.clusters[sel]
    ? `community ${g.clusters[sel].id} \u00b7 ${g.clusters[sel].size} nodes` + (g.clusters[sel].members?.length ? " \u00b7 " + g.clusters[sel].members.slice(0, 5).join(", ") : "")
    : "click a community to highlight";

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {[["Nodes", g.stats.nodes], ["Edges", g.stats.edges], ["Communities", g.stats.communities], ["Entities", g.stats.entities], ["Facts", g.stats.facts]].map(([k, v]) => (
            <span key={k} className="rounded-lg border border-border bg-surface-2 px-2.5 py-1 font-mono text-[11.5px] text-muted">
              {k.toUpperCase()} <b className="text-foreground">{v}</b>
            </span>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
          <div className="overflow-hidden rounded-xl border border-border bg-surface-2">
            <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Community graph" className="h-auto w-full">
              <rect width={W} height={H} style={{ fill: "var(--color-surface-2)" }} />
              {arcs}
              {dots}
            </svg>
          </div>
          <div className="flex flex-col gap-1.5">
            <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">
              Communities ({g.clusters.length})
            </h2>
            <div className="flex max-h-[420px] flex-col gap-0.5 overflow-y-auto pr-1">{legend}</div>
            <p className="mt-1 font-mono text-[11px] text-subtl">{selDetails}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Graph() {
  const [g, setG] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null);

  useEffect(() => {
    loadGraph().then(setG).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="flex max-w-5xl flex-col gap-5">
      <header className="flex flex-col gap-1">
        <h1 className="text-[26px] font-semibold tracking-[-0.02em]">Knowledge graph</h1>
        <p className="text-[13px] text-muted">Entities and keywords stitched from your sources, clustered by Louvain.</p>
      </header>

      {err && <p className="text-[13px] text-warn">{err}</p>}
      {!err && !g && <Skeleton className="h-96 w-full" />}
      {!err && g && !g.built && <p className="text-[13px] text-warn">No graph yet. Rebuild the twin first.</p>}
      {!err && g && g.built && <GraphCard g={g} sel={sel} setSel={setSel} />}
    </div>
  );
}