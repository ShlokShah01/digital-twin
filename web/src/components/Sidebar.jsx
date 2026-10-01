import { useEffect, useRef, useState } from "react";
import {
  ArrowCounterClockwise,
  Archive,
  ChatText,
  PencilSimple,
  Trash,
} from "@phosphor-icons/react";
import { cn } from "cn";
import { matchesConversation } from "../lib/history.js";

function SectionLabel({ children }) {
  return (
    <div className="mt-4 mb-1 px-3 text-[11px] font-medium uppercase tracking-[0.08em] text-subtl">
      {children}
    </div>
  );
}

function SessionRow({ s, active, onSelect, onRename, onToggleArchive, onDelete }) {
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState(s.title);
  const inputRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
  }, [renaming]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const commitRename = () => {
    onRename(s.id, draft.trim() || s.title);
    setRenaming(false);
  };

  const askDelete = () => {
    if (confirming) {
      clearTimeout(timerRef.current);
      onDelete(s.id);
    } else {
      setConfirming(true);
      timerRef.current = setTimeout(() => setConfirming(false), 2600);
    }
  };

  return (
    <div
      className={cn(
        "group flex items-center gap-1.5 rounded-lg py-1.5 pl-2.5 pr-1.5 text-[12.5px] transition-colors",
        active ? "bg-surface-2 text-foreground" : "text-muted hover:bg-surface hover:text-foreground",
      )}
    >
      <ChatText size={14} className={cn("shrink-0", active ? "text-accent" : "text-subtl")} />
      {renaming ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setRenaming(false);
          }}
          className="min-w-0 flex-1 rounded-md border border-border-strong bg-surface-3 px-1.5 py-0.5 font-mono text-[11.5px] text-foreground focus-visible:border-ring"
          aria-label="Session name"
        />
      ) : (
        <button
          type="button"
          onClick={() => onSelect(s.id)}
          className="min-w-0 flex-1 truncate text-left"
          title={s.title}
        >
          {s.title || "New chat"}
        </button>
      )}
      {!renaming && (
        <span className="flex shrink-0 items-center gap-0.5 max-md:opacity-100 md:opacity-0 md:focus-within:opacity-100 md:group-hover:opacity-100">
          <button
            type="button"
            onClick={() => setRenaming(true)}
            className="grid size-5 place-items-center rounded text-subtl hover:text-foreground"
            title="Rename"
            aria-label={"Rename " + (s.title || "chat")}
          >
            <PencilSimple size={13} />
          </button>
          <button
            type="button"
            onClick={() => onToggleArchive(s.id)}
            className="grid size-5 place-items-center rounded text-subtl hover:text-foreground"
            title={s.archived ? "Restore" : "Archive"}
            aria-label={s.archived ? "Restore session" : "Archive session"}
          >
            {s.archived ? <ArrowCounterClockwise size={13} /> : <Archive size={13} />}
          </button>
          <button
            type="button"
            onClick={askDelete}
            className={cn(
              "grid h-5 place-items-center rounded px-1 text-[10.5px]",
              confirming
                ? "bg-destructive/15 text-destructive"
                : "text-subtl hover:text-destructive",
            )}
            title={confirming ? "Click again to delete" : "Delete"}
            aria-label={"Delete " + (s.title || "chat")}
          >
            {confirming ? "Delete?" : <Trash size={13} />}
          </button>
        </span>
      )}
    </div>
  );
}

export default function Sidebar({
  store,
  activeId,
  onSelect,
  onRename,
  onArchive,
  onDelete,
}) {
  const [query, setQuery] = useState("");
  const matches = store.list.filter(s => matchesConversation(s, query));
  const live = matches.filter((s) => !s.archived).sort((a, b) => b.updatedAt - a.updatedAt);
  const archived = matches.filter((s) => s.archived).sort((a, b) => b.updatedAt - a.updatedAt);

  return (
      <div className="rail-sessions flex-1 overflow-y-auto pb-2">
        <div className="session-search"><label className="sr-only" htmlFor="session-search">Search conversations</label><input id="session-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search conversations" /></div>
        {query.trim() && matches.length === 0 && <p className="px-3 py-2 text-[12px] text-muted" role="status">No matching conversations.</p>}
        <SectionLabel>Recent ({live.length})</SectionLabel>
        <div className="flex flex-col gap-0.5">
          {live.length === 0 && !query.trim() && (
            <p className="px-3 py-1 text-[12px] text-subtl">No sessions yet. Start one above.</p>
          )}
          {live.map((s) => (
            <SessionRow
              key={s.id}
              s={s}
              active={s.id === activeId}
              onSelect={onSelect}
              onRename={onRename}
              onToggleArchive={(id) => onArchive(id, true)}
              onDelete={onDelete}
            />
          ))}
        </div>
        {archived.length > 0 && (
          <>
            <SectionLabel>Archived ({archived.length})</SectionLabel>
            <div className="flex flex-col gap-0.5">
              {archived.map((s) => (
                <SessionRow
                  key={s.id}
                  s={s}
                  active={s.id === activeId}
                  onSelect={onSelect}
                  onRename={onRename}
                  onToggleArchive={(id) => onArchive(id, false)}
                  onDelete={onDelete}
                />
              ))}
            </div>
          </>
        )}
      </div>
  );
}
