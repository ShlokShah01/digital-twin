import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { ArrowsClockwise, PenNib, Plus, GearSix, List, SquaresFour, ChatCircle, UserCircle, Graph as GraphIcon, BookOpen, ArrowUpRight, CaretRight, X, CaretUp } from "@phosphor-icons/react";
import { toast, Toaster } from "sonner";
import { loadHealth, loadProfile, rebuild } from "./api.js";
import { Button } from "./components/ui/button.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useChatStore } from "./lib/chat.js";
import Home from "./views/Home.jsx";
import Chat from "./views/Chat.jsx";
import Profile from "./views/Profile.jsx";
import Graph from "./views/Graph.jsx";
import How from "./views/How.jsx";
import Resources from "./views/Resources.jsx";
import Settings from "./views/Settings.jsx";
import { loadPreferences, normalizePreferences } from "./lib/preferences.js";

const VIEWS = [
  { id: "home", label: "Overview", icon: SquaresFour },
  { id: "chat", label: "Chat", icon: ChatCircle },
  { id: "profile", label: "Profile", icon: UserCircle },
  { id: "graph", label: "Knowledge graph", icon: GraphIcon },
  { id: "how", label: "How it works", icon: BookOpen },
  { id: "resources", label: "Resources", icon: BookOpen },
  { id: "settings", label: "Settings", icon: GearSix },
];

const current = () => {
  let name = (location.hash || "#/home").replace("#/", "").split("?")[0];
  if (name === "ask") name = "chat";
  return VIEWS.some((v) => v.id === name) ? name : "home";
};

function StatusChip({ health }) {
  const ok = health?.twin_built;
  return (
    <span className="hidden items-center gap-2 rounded-full border border-border bg-surface px-2 py-1 font-mono text-[11px] text-muted sm:inline-flex">
      <span className={ok ? "size-1.5 rounded-full bg-accent" : "size-1.5 rounded-full bg-warn"} />
      twin {ok ? "built" : "empty"}
      <span className="text-subtl">/</span>
      chunks {health?.chunks ?? "\u2013"}
      <span className="text-subtl">/</span>
      llm {health?.llm ? "on" : "off"}
    </span>
  );
}

export default function App() {
  const [view, setView] = useState(current());
  const [preferences, setPreferences] = useState(loadPreferences);
  const [mobileView, setMobileView] = useState(() => window.matchMedia("(max-width: 767px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const update = () => setMobileView(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const p = normalizePreferences(preferences);
    document.documentElement.dataset.theme = p.theme;
    document.documentElement.dataset.textSize = p.textSize;
    document.documentElement.dataset.graphPalette = p.graphPalette;
    document.documentElement.dataset.motion = p.motion ? "on" : "off";
    try { localStorage.setItem("digital-twin.preferences", JSON.stringify(p)); } catch {}
  }, [preferences]);
  const [health, setHealth] = useState(null);
  const [profile, setProfile] = useState(null);
  const [busy, setBusy] = useState(false);
  const didLoad = useRef(false);
  const didFocus = useRef(false);
  const mainRef = useRef(null);
  const railRef = useRef(null);
  const railToggleRef = useRef(null);
  const profileMenuRef = useRef(null);

  const store = useChatStore();
  const [activeId, setActiveId] = useState(store.list.find((s) => !s.archived)?.id || null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      const raw = localStorage.getItem("digital-twin.sidebarCollapsed");
      return raw ? raw === "1" : false;
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const previouslyOpen = useRef(false);
  useEffect(() => {
    if (previouslyOpen.current && !mobileOpen) railToggleRef.current?.focus();
    previouslyOpen.current = mobileOpen;
  }, [mobileOpen]);
  useEffect(() => {
    const closeMenu = event => {
      const menu=profileMenuRef.current;
      if(menu?.open && !menu.contains(event.target)) menu.open=false;
    };
    document.addEventListener("pointerdown",closeMenu);
    return () => document.removeEventListener("pointerdown",closeMenu);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("digital-twin.sidebarCollapsed", sidebarCollapsed ? "1" : "0");
    } catch {}
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (view !== "chat") return;
    const hasDraft = (() => {
      try {
        return !!sessionStorage.getItem("draft-question");
      } catch {
        return false;
      }
    })();
    if (hasDraft) setActiveId(store.create());
    else if (!activeId) setActiveId(store.create());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  useEffect(() => {
    const onHash = () => setView(current());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!didFocus.current) {
      didFocus.current = true;
      return;
    }
    mainRef.current?.focus({ preventScroll: true });
  }, [view]);

  useEffect(() => {
    if (didLoad.current) return;
    didLoad.current = true;
    loadHealth().then(setHealth).catch(() => {});
    loadProfile().then(setProfile).catch(() => {});
  }, []);

  const onRebuild = async () => {
    setBusy(true);
    toast.loading("Rebuilding your twin from its source files…", {
      id: "rebuild",
    });
    try {
      const res = await rebuild();
      toast.success(
        `Built: ${res.documents} documents \u00b7 ${res.chunks} chunks \u00b7 ${res.graph.communities} communities`,
        { id: "rebuild" },
      );
      setHealth(await loadHealth());
      setProfile(await loadProfile());
    } catch (e) {
      toast.error("Build failed: " + e.message, { id: "rebuild", duration: 6000 });
    } finally {
      setBusy(false);
    }
  };

  const go = (next) => { location.hash = "/" + next; setView(next); };

  const onNewChat = () => {
    go("chat");
    const id = store.create();
    setActiveId(id);
    setMobileOpen(false);
  };

  const onOpenChat = (id) => {
    go("chat");
    setActiveId(id);
    setMobileOpen(false);
  };

  const onArchiveSession = (id, archived) => {
    if (archived) store.archive(id);
    else store.unarchive(id);
    if (archived && id === activeId) {
      const next = store.list.find((s) => !s.archived && s.id !== id);
      setActiveId(next?.id || null);
    }
  };

  const onDeleteSession = (id) => {
    const wasActive = id === activeId;
    const next = store.list.find((s) => !s.archived && s.id !== id);
    store.remove(id);
    if (wasActive) setActiveId(next?.id || null);
  };

  const viewComponent = {
    home: <Home health={health} profile={profile} busy={busy} notify={go} />,
    chat: (
      <Chat
        store={store}
        preferences={preferences}
        activeId={activeId}
        setActiveId={setActiveId}
      />
    ),
    profile: <Profile profile={profile} onProfile={setProfile} />,
    graph: <Graph />,
    how: <How />,
    resources: <Resources />,
    settings: <Settings preferences={preferences} onChange={setPreferences} health={health} />,
  }[view];

  return (
    <MotionConfig reducedMotion="user">
      <div className={"app-frame single-rail" + (sidebarCollapsed ? " rail-collapsed" : "")}>
        <a href="#main" className="skip-link" onClick={(e) => {
          e.preventDefault(); mainRef.current?.focus();
        }}>Skip to content</a>
        {mobileOpen && <div className="rail-backdrop" onClick={() => setMobileOpen(false)} aria-hidden="true"/>}
        <aside ref={railRef} className={"workspace-rail" + (mobileOpen ? " is-open" : "")} aria-label="Chat and navigation" onKeyDown={e => {
          if (e.key === "Escape") { setMobileOpen(false); if (profileMenuRef.current) profileMenuRef.current.open=false; railToggleRef.current?.focus(); }
          if (mobileOpen && e.key === "Tab") {
            const controls=Array.from(railRef.current.querySelectorAll('a[href],button,summary,input')).filter(el=>!el.disabled && el.getClientRects().length);
            const first=controls[0], last=controls.at(-1);
            if(e.shiftKey && document.activeElement===first){e.preventDefault();last?.focus();}
            else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first?.focus();}
          }
        }}>
          <Button variant="ghost" size="icon" className="rail-close" aria-label="Close navigation" onClick={() => {setMobileOpen(false);railToggleRef.current?.focus();}}><X size={18}/></Button>
          <a className="brand" href="#/home" aria-label="My Digital Twin home">
            <span className="brand-mark" aria-hidden="true"><PenNib size={22} weight="duotone" /></span>
            <span>Digital Twin</span>
          </a>
          <Button className="rail-new" onClick={onNewChat}><Plus size={18} />New conversation</Button>
          <Sidebar store={store} activeId={activeId} onSelect={onOpenChat} onRename={store.rename}
            onArchive={onArchiveSession} onDelete={onDeleteSession} />
          <details ref={profileMenuRef} className="profile-menu">
            <summary aria-label="Open profile and pages"><span className="person-avatar profile-brand" aria-hidden="true"><PenNib size={18} weight="regular" /></span><span>Your profile</span><CaretUp size={15}/></summary>
            <nav aria-label="Profile pages" className="profile-pages">
              {VIEWS.map(({id,label,icon:Icon}) => <a key={id} href={"#/"+id} aria-label={label} aria-current={view===id ? "page" : undefined} onClick={() => { profileMenuRef.current.open=false; setMobileOpen(false); }}><Icon size={18}/><span>{label}</span></a>)}
              <Button variant="ghost" onClick={onRebuild} disabled={busy}><ArrowsClockwise size={18}/>{busy ? "Rebuilding…" : "Rebuild from sources"}</Button>
            </nav>
          </details>
        </aside>
        <div className="workspace" inert={mobileOpen ? true : undefined}>
          <header className="workspace-header">
            <div className="workspace-path"><span className="mobile-brand"><PenNib size={20} /></span><span>{view === "chat" ? "Conversation" : VIEWS.find(v => v.id === view)?.label}</span></div>
            <div className="header-actions">
              <Button ref={railToggleRef} variant="ghost" size="icon" aria-label="Toggle navigation" aria-expanded={mobileView ? mobileOpen : !sidebarCollapsed} onClick={() => {
                if (mobileView) {setMobileOpen(true); requestAnimationFrame(()=>railRef.current?.querySelector('button')?.focus());}
                else setSidebarCollapsed(v=>!v);
              }}><List size={19}/></Button>
              {view !== "chat" && <span className="header-health"><span className={health?.twin_built ? "status-dot" : "status-dot waiting"} />{health ? health.twin_built ? "Ready" : "Build needed" : "Connecting"}</span>}
              <Button variant="outline" size="sm" className="mobile-rebuild" onClick={onRebuild} disabled={busy}><ArrowsClockwise size={15} />Rebuild</Button>
            </div>

          </header>
          <main ref={mainRef} id="main" tabIndex={-1} className="workspace-main">
            {view === "chat" ? (
              <div className="chat-layout">
                <div className="chat-page">{viewComponent}</div>
              </div>
            ) : <div className={"view-page view-" + view}>{viewComponent}</div>}
          </main>
          {view !== "chat" && <footer className="workspace-footer"><span>Personal evidence. Thoughtful decisions.</span><span>Demo twin · Predictions are not advice.</span></footer>}
        </div>
        <Toaster position="bottom-center" richColors closeButton />
      </div>
    </MotionConfig>
  );
}
