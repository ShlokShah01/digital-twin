import { Card, CardContent } from "../components/ui/card.jsx";

const steps = [
  ["Load raw writing", "txt / md / json / csv files about you (journal, preferences, survey answers)."],
  ["Chunk & embed", "each document split into ~150-word chunks, embedded with FastEmbed (BAAI/bge-small-en-v1.5), stored in LanceDB."],
  ["Mine the profile", "an LLM (or the offline heuristic miner) extracts facts, stance, preferences, decision patterns and a first-person persona."],
  ["Knowledge graph", "entities, keywords and chunks become nodes; co-occurrence edges are built and clustered with Louvain communities for GraphRAG retrieval."],
];

export default function How() {
  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <header className="flex flex-col gap-1">
        <h1 className="text-[26px] font-semibold tracking-[-0.02em]">How it works</h1>
        <p className="text-[13px] text-muted">The pipeline that turns raw writing into a twin that prefers and decides like you.</p>
      </header>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Pipeline</h2>
          <ol className="flex flex-col gap-0">
            {steps.map(([t, d], i) => (
              <li key={t} className="flex gap-3 py-2.5">
                <span className="w-6 shrink-0 font-mono text-[11px] text-accent">{(i + 1).toString().padStart(2, "0")}</span>
                <span className="text-[13px] leading-relaxed">
                  <b>{t}:</b> {d}
                </span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">How a decision is made</h2>
          <p className="text-[13px] text-muted">When you ask with choices, two independent heads vote:</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 rounded-xl border border-border bg-surface-2 p-3.5">
              <h3 className="font-mono text-[12px] text-accent">Laya</h3>
              <p className="text-[12.5px] leading-relaxed text-muted">
                a cross-platform causal-decision model calibrates preference distributions over the choices and reranks retrieved chunks (offline, no key needed).
              </p>
            </div>
            <div className="flex flex-col gap-1 rounded-xl border border-border bg-surface-2 p-3.5">
              <h3 className="font-mono text-[12px] text-accent">LLM</h3>
              <p className="text-[12.5px] leading-relaxed text-muted">
                optional. Retrieves the most relevant chunks via vector + GraphRAG, then reasons in first person as the persona and returns normalized probabilities.
              </p>
            </div>
          </div>
          <p className="text-[12.5px] leading-relaxed text-muted">
            The final ensemble is the arithmetic mean of the two distributions. Confidence blends{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11.5px]">0.6 {"\u00d7"} LLM + 0.4 {"\u00d7"} Laya</code> on agreement; on{" "}
            <i>conflict</i> the LLM wins with an explicit caution note. With only one choice (or none) the twin refuses to vote: a single option is not a contest.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Modes</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 rounded-xl border border-border bg-surface-2 p-3.5">
              <h3 className="font-mono text-[12px] text-warn">Offline</h3>
              <p className="text-[12.5px] leading-relaxed text-muted">
                no OPENAI_API_KEY? Set DIGITAL_TWIN_NO_LLM=1 (or pass --no-llm). Heuristic miner + Laya only; still answers with probabilities and GraphRAG context.
              </p>
            </div>
            <div className="flex flex-col gap-1 rounded-xl border border-border bg-surface-2 p-3.5">
              <h3 className="font-mono text-[12px] text-accent">LLM</h3>
              <p className="text-[12.5px] leading-relaxed text-muted">
                set OPENAI_API_KEY in .env. The twin extracts, writes the persona, summarizes communities and reasons in the first person.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">CLI</h2>
          <pre className="overflow-x-auto rounded-xl bg-surface-3 p-3.5 font-mono text-[11.5px] leading-relaxed text-muted">
{`digital-twin build --data data\\raw\\demo --no-llm
digital-twin ask "Should I buy refurbished?" ^
  --options "Buy flagship;Buy certified refurbished;Wait"`}
          </pre>
          <p className="text-[12px] text-subtl">
            PowerShell note: pass all choices as one quoted string separated by ;. A semicolon between two quoted strings is a statement separator, not an option split.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Local web app</h2>
          <pre className="overflow-x-auto rounded-xl bg-surface-3 p-3.5 font-mono text-[11.5px] leading-relaxed text-muted">
{`digital-twin serve --port 8000
# or, for UI development:
cd web && npm run dev`}
          </pre>
          <p className="text-[12px] text-muted">
            API: <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/health</code>,{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/profile</code>,{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/graph</code>,{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/build</code>,{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/ingest</code>,{" "}
            <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px]">/api/ask</code>.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-2">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">Notes</h2>
          <ul className="list-disc space-y-1.5 pl-4 text-[12.5px] leading-relaxed text-muted">
            <li>The React UI builds with Vite into web/dist; the server serves it automatically, with /assets mounted for the hashed bundle.</li>
            <li>Full offline path is covered by the pytest suite (tests/), including a local mock OpenAI server under tests/mocks/. LLM behavior is tested without a real key.</li>
            <li>Laya's typed-decisions checkpoint may warn about uncalibrated temperatures; on low-memory machines a heavy in-process build followed by Laya load can raise os error 1455; the twin degrades gracefully to template answers.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}