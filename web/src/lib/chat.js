import { useEffect, useMemo, useState } from "react";

const KEY = "digital-twin.chat.v1";
const MAX_SESSIONS = 80;
const MAX_MESSAGES = 60;

export function uid() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "id-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function titleFrom(text) {
  const s = String(text || "").trim().replace(/\s+/g, " ");
  if (!s) return "New chat";
  const words = s.split(" ").slice(0, 7).join(" ");
  return words.length > 48 ? words.slice(0, 47) + "\u2026" : words;
}

function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function write(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_SESSIONS)));
  } catch {}
}

export function useChatStore() {
  const [sessions, setSessions] = useState(read);

  useEffect(() => {
    write(sessions);
  }, [sessions]);

  const store = useMemo(
    () => ({
      list: sessions,
      create() {
        const id = uid();
        const session = {
          id,
          title: "",
          renamed: false,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          archived: false,
          messages: [],
        };
        setSessions((list) => [session, ...list]);
        return id;
      },
      rename(id, title) {
        const t = String(title || "").trim();
        setSessions((list) =>
          list.map((s) => (s.id === id ? { ...s, title: t || s.title, renamed: true } : s)),
        );
      },
      archive(id) {
        setSessions((list) => list.map((s) => (s.id === id ? { ...s, archived: true } : s)));
      },
      unarchive(id) {
        setSessions((list) =>
          list.map((s) => (s.id === id ? { ...s, archived: false, updatedAt: Date.now() } : s)),
        );
      },
      remove(id) {
        setSessions((list) => list.filter((s) => s.id !== id));
      },
      pushMessage(id, message) {
        setSessions((list) =>
          list.map((s) =>
            s.id === id
              ? {
                  ...s,
                  updatedAt: Date.now(),
                  title: s.title ? s.title : titleFrom(message.question || ""),
                  messages: [...s.messages, message].slice(-MAX_MESSAGES),
                }
              : s,
          ),
        );
      },
      patchMessage(id, messageId, patch) {
        setSessions((list) =>
          list.map((s) =>
            s.id === id
              ? {
                  ...s,
                  messages: s.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
                }
              : s,
          ),
        );
      },
    }),
    [sessions],
  );

  return store;
}