import { useEffect, useState } from "react";
import { loadProfile, chunkText } from "../api.js";
import { Card, CardContent } from "../components/ui/card.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { Skeleton } from "../components/ui/skeleton.jsx";
import { Separator } from "../components/ui/separator.jsx";

function Stat({ k, v, mono = true }) {
  return (
    <Card className="gap-0">
      <CardContent className="flex flex-col gap-1 py-3">
        <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">{k}</span>
        <span className={mono ? "font-mono text-[13px] text-foreground" : "text-[13px] text-foreground"}>{v}</span>
      </CardContent>
    </Card>
  );
}

export default function Profile({ profile, onProfile }) {
  const [err, setErr] = useState("");

  useEffect(() => {
    if (profile) return;
    loadProfile().then(onProfile).catch(() => setErr("No twin built yet."));
  }, [profile, onProfile]);

  if (!profile) {
    if (err !== "No twin built yet.") {
      return (
        <div className="flex max-w-3xl flex-col gap-5">
          <h1 className="text-[26px] font-semibold tracking-[-0.02em]">Profile</h1>
          <p className="text-[13px] text-muted">{err || "Loading\u2026"}</p>
          <div className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      );
    }
    return (
      <div className="flex max-w-3xl flex-col gap-5">
        <h1 className="text-[26px] font-semibold tracking-[-0.02em]">Profile</h1>
        <Card>
          <CardContent className="flex flex-col gap-2">
            <p className="text-[13px] text-warn">{err}</p>
            <p className="text-[12.5px] leading-relaxed text-muted">
              Press <b className="text-foreground">Rebuild</b> in the top bar, or run{" "}
              <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11.5px] text-accent">
                digital-twin build
              </code>{" "}
              from the CLI. The heuristic miner needs no LLM key and derives a persona, topics, and
              preferences from your raw text.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const p = profile;
  const st = p.stats || {};

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-[26px] font-semibold tracking-[-0.02em]">{p.name || "Unnamed"}</h1>
        {p.built_at && (
          <Badge variant="outline" className="font-mono text-[10.5px]">
            built {new Date(p.built_at).toLocaleString()}
          </Badge>
        )}
      </header>

      {p.persona && (
        <Card>
          <CardContent className="flex flex-col gap-1.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Persona</span>
            <p className="text-[14px] leading-relaxed text-foreground">{p.persona}</p>
          </CardContent>
        </Card>
      )}

      {(p.topics?.length || 0) > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-2.5">
            <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Topics</h2>
            <div className="flex flex-wrap gap-1.5">
              {p.topics.map(([t, s]) => (
                <Badge key={t} variant="secondary">
                  {t}
                  {s != null ? <span className="text-subtl">{"\u00b7"} {(s * 100).toFixed(0)}%</span> : null}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {(p.preferences?.length || 0) > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Preferences</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {p.preferences.map((pr, i) => (
                <div key={i} className="flex flex-col gap-1.5 rounded-xl border border-border bg-surface-2 p-3.5">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {pr.domain || "general"}
                    </Badge>
                    {pr.strength != null && (
                      <span className="font-mono text-[11px] text-subtl">{pr.strength.toFixed(2)}</span>
                    )}
                  </div>
                  <p className="text-[12.5px] leading-relaxed text-foreground">{chunkText(pr.statement, 160)}</p>
                  {(pr.examples?.length || 0) > 0 && (
                    <p className="text-[11.5px] text-subtl">{chunkText(pr.examples.join("; "), 120)}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {(p.decision_patterns?.length || 0) > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Decision patterns</h2>
            {p.decision_patterns.map((d, i) => (
              <div key={i} className="flex flex-col gap-1">
                <div className="text-[13.5px] font-medium">{d.name}</div>
                {d.trigger && <div className="font-mono text-[11.5px] text-subtl">trigger: {d.trigger}</div>}
                <div className="text-[12.5px] text-muted">{chunkText(d.behavior, 200)}</div>
                {(d.examples?.length || 0) > 0 && (
                  <div className="text-[11.5px] text-subtl">e.g. {chunkText(d.examples.join("; "), 120)}</div>
                )}
                {i < p.decision_patterns.length - 1 && <Separator className="mt-2" />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {p.style?.n_words && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Writing style</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat k="Formality" v={p.style.formality != null ? p.style.formality.toFixed(2) : "\u2013"} />
              <Stat k="Vocabulary" v={p.style.vocabulary ?? "\u2013"} />
              <Stat k="Avg sentence" v={p.style.mean_sentence_len != null ? p.style.mean_sentence_len.toFixed(1) + "w" : "\u2013"} />
              <Stat k="TTR" v={p.style.ttr != null ? p.style.ttr.toFixed(2) : "\u2013"} />
              <Stat k="Sentiment" v={p.style.sentiment_mean != null ? p.style.sentiment_mean.toFixed(2) : "\u2013"} />
              <Stat k="1st person" v={p.style.first_person_rate != null ? p.style.first_person_rate.toFixed(1) + "/100w" : "\u2013"} />
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Build stats</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[["Documents", st.n_documents], ["Chunks", st.n_chunks], ["Words", st.n_words], ["Facts", st.n_facts], ["Entities", st.n_entities], ["Preferences", st.n_preferences], ["Patterns", st.n_patterns]].map(([k, v]) => (
              <Stat key={k} k={k} v={v ?? "\u2013"} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}