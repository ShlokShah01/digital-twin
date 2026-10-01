import { useEffect, useRef, useState } from "react";
import {
  SpeakerHigh,
  DownloadSimple,
  PenNib,
  CircleNotch,
  PaperPlaneTilt,
  Microphone,
  Stop,
  Plus,
} from "@phosphor-icons/react";
import { askStream, splitOptions } from "../api.js";
import { downloadConversation } from "../lib/history.js";
import { uid } from "../lib/chat.js";
import { voiceDraft, replyUtterance, readyVoices } from "../lib/voice.js";
import { Button } from "../components/ui/button.jsx";
import { Textarea } from "../components/ui/textarea.jsx";

function AnswerCard({ msg, onRetry, retrying, timings, speechSupported, reading, onRead, speechNotice }) {
  return (
    <div className="plain-answer">
      {msg.error ? (
        <div className="chat-error" role="alert">
          <p>Couldn't send your message. {msg.error}</p>
          <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
            <CircleNotch size={14} className={retrying ? "animate-spin" : ""} />Retry
          </Button>
        </div>
      ) : <p className="answer-prose">{msg.answer?.answer || "No answer was returned. Please try again."}</p>}
      {!msg.error && msg.answer?.answer && <div className="reply-audio"><Button variant="ghost" size="sm" disabled={!speechSupported} aria-pressed={reading} onClick={onRead} title={speechSupported ? "Listen to this answer" : "Read aloud is unavailable in this browser"}>
        {reading ? <Stop size={15} /> : <SpeakerHigh size={16} />}<span>{reading ? "Stop reading" : "Read aloud"}</span>
      </Button>{speechNotice && <small role="status">{speechNotice}</small>}</div>}
      {timings && !msg.error && Number.isFinite(msg.duration) && <small className="reply-timing">Answered in {(msg.duration / 1000).toFixed(1)} seconds</small>}
    </div>
  );
}

const STARTERS = [
  {
    t: "Help me choose",
    q: "New laptop: a flagship 16-inch or a certified refurbished 14-inch?",
    o: "Buy the new flagship 16-inch\nGet a certified refurbished 14-inch with warranty\nWait a month",
  },
  {
    t: "What patterns do I repeat?",
    q: "What decision patterns do I keep repeating?",
    o: "",
  },
  {
    t: "How do I weigh money?",
    q: "How do I weigh money against convenience?",
    o: "",
  },
  {
    t: "What would I do?",
    q: "I am torn between joining the group or staying home. What would I do?",
    o: "Join the group\nStay home",
  },
];

export default function Chat({ store, activeId, setActiveId, preferences }) {
  const [readingId, setReadingId] = useState(null);
  const [speechNotice, setSpeechNotice] = useState(null);
  const utteranceRef = useRef(null);
  const canRead = !!(window.speechSynthesis && window.SpeechSynthesisUtterance);
  const stopReading = () => {
    if (utteranceRef.current) {
      utteranceRef.current = null;
      window.speechSynthesis?.cancel();
    }
    setReadingId(null);
  };
  useEffect(() => {
    stopReading();
    setSpeechNotice(null);
    return () => {
      if (utteranceRef.current) {
        utteranceRef.current = null;
        window.speechSynthesis?.cancel();
      }
    };
  }, [activeId]);
  const readReply = async msg => {
    const wasReading = readingId === msg.id;
    stopReading();
    setSpeechNotice(null);
    if (wasReading || !canRead) return;
    recognitionRef.current?.abort();
    const waiting = {};
    utteranceRef.current = waiting;
    setReadingId(msg.id);
    const voices = await readyVoices(window.speechSynthesis);
    if (utteranceRef.current !== waiting) return;
    const utterance = replyUtterance(msg.answer.answer, window.SpeechSynthesisUtterance, voices);
    utteranceRef.current = utterance;
    const finish = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      setReadingId(null);
    };
    utterance.onend = finish;
    utterance.onerror = event => {
      if (utteranceRef.current !== utterance) return;
      finish();
      if (!["canceled", "interrupted"].includes(event.error)) setSpeechNotice({ id: msg.id, text: "Audio could not play. Check your device's voices and sound settings, then try again." });
    };
    setReadingId(msg.id);
    try { window.speechSynthesis.speak(utterance); }
    catch { finish(); setSpeechNotice({ id: msg.id, text: "Read aloud is unavailable. Try Chrome or Edge." }); }
  };
  const [text, setText] = useState("");
  const [opts, setOpts] = useState("");
  const [showOpts, setShowOpts] = useState(false);
  const [pending, setPending] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [voiceLang, setVoiceLang] = useState("hi-IN");
  const recognitionRef = useRef(null);
  const speechSupported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  useEffect(() => () => {
    const recognition = recognitionRef.current;
    if (recognition) {
      recognition.onresult = recognition.onend = recognition.onerror = null;
      recognition.abort();
    }
  }, []);
  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = "auto";
    inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 112) + "px";
  }, [text]);
  useEffect(() => { recognitionRef.current?.abort(); }, [activeId]);
  const toggleVoice = () => {
    if (listening) { recognitionRef.current?.stop(); return; }
    stopReading();
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { setVoiceError("Voice typing isn't supported here. Open this chat in Chrome or Edge."); return; }
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    recognition.lang = voiceLang;
    recognition.interimResults = true;
    recognition.continuous = true;
    const original = text.trimEnd();
    setVoiceError("");
    recognition.onresult = event => {
      setText(voiceDraft(original, event.results));
    };
    recognition.onerror = event => {
      setVoiceError(event.error === "not-allowed" ? "Microphone access was blocked. Allow it in your browser, then try again."
        : event.error === "no-speech" ? "No speech detected. Tap the mic and try again."
        : "Voice typing stopped. Check your microphone and connection, then try again.");
      setListening(false);
    };
    recognition.onend = () => { setListening(false); inputRef.current?.focus(); };
    try { recognition.start(); setListening(true); }
    catch { setVoiceError("Could not start voice typing. Try again."); }
  };
  useEffect(() => {
    if (!pending) return;
    const start = Date.now(); setElapsed(0);
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [pending]);
  const [drafts, setDrafts] = useState(() => ({
    q: sessionStorage.getItem("draft-question") || "",
    o: sessionStorage.getItem("draft-options") || "",
  }));
  const inputRef = useRef(null);
  const endRef = useRef(null);
  const smoothRef = useRef(
    typeof window !== "undefined" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  const session = store.list.find((s) => s.id === activeId);

  const scrollToEnd = () => {
    const el = endRef.current;
    if (el) el.scrollIntoView({ behavior: smoothRef.current && preferences?.motion !== false ? "smooth" : "auto", block: "end" });
  };

  useEffect(() => {
    scrollToEnd();
  }, [session?.messages.length, pending]);

  useEffect(() => {
    if (session && session.messages.length === 0 && drafts.q) {
      const { q, o } = drafts;
      setDrafts({ q: "", o: "" });
      send(session.id, q, o);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  const send = async (id, question, options) => {
    const qu = question.trim();
    if (!qu || pending || listening) return;
    const o = splitOptions(options);
    sessionStorage.removeItem("draft-question");
    sessionStorage.removeItem("draft-options");
    setPending(true);
    setText("");
    setOpts("");
    const userMsg = { id: uid(), role: "user", question: qu, options: o, ts: Date.now() };
    const thinkMsg = { id: uid(), role: "assistant", question: qu, options: o, thinking: true, ts: Date.now() };
    const started = performance.now();
    store.pushMessage(id, userMsg);
    store.pushMessage(id, thinkMsg);
    try {
      let firstToken, lastPreview = "", lastPaint = 0;
      const ans = await askStream(qu, o, preview => {
        if (preview && firstToken == null) firstToken = performance.now() - started;
        const now = performance.now();
        if (preview !== lastPreview && (!preview || now - lastPaint > 50)) {
          lastPreview = preview; lastPaint = now;
          store.patchMessage(id, thinkMsg.id, { preview, firstToken });
        }
      });
      store.patchMessage(id, thinkMsg.id, { thinking: false, answer: ans, duration: performance.now() - started });
      if (preferences?.notifications && document.hidden && typeof Notification !== "undefined" && Notification.permission === "granted") {
        try { new Notification("Digital Twin", { body: "Your answer is ready. Return to your conversation to read it.", tag: "digital-twin-reply" }); } catch {}
      }
    } catch (e) {
      store.patchMessage(id, thinkMsg.id, { thinking: false, error: e.message });
    } finally {
      setPending(false);
    }
  };

  const startChat = (q, o) => {
    const id = store.create();
    setActiveId(id);
    send(id, q || text, o ?? opts);
  };

  const retry = (msg) => {
    setRetrying(true);
    (async () => {
      try {
        await send(session.id, msg.question, (msg.options || []).join("\n"));
      } finally {
        setRetrying(false);
      }
    })();
  };

  const messages = session?.messages || [];
  const submit = () => session ? send(session.id, text, opts) : startChat(text, opts);
  return (
    <div className="conversation">
      {messages.length > 0 && <div className="conversation-actions"><Button variant="ghost" size="sm" disabled={pending} onClick={() => downloadConversation(session)}><DownloadSimple size={16} />Export chat</Button></div>}
      <div className="conversation-heading"><h1>{session?.title || "Chat"}</h1></div>
      <div className="conversation-scroll" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text" aria-busy={pending}>
        {messages.length === 0 && <div className="chat-welcome">
          <span className="welcome-symbol" aria-hidden="true"><PenNib size={36} weight="duotone" /></span>
          <h2>How can I help?</h2>
          <p>Ask a question or talk it through.</p>
          <div className="welcome-prompts">{STARTERS.map(s => <button key={s.t} type="button" onClick={() => {
            setText(s.q); setOpts(s.o); setShowOpts(!!s.o); inputRef.current?.focus();
          }}><span>{s.t}</span><Plus size={16} /></button>)}</div>
        </div>}
        {messages.map(msg => msg.role === "user" ? (
          <div key={msg.id} className="user-turn"><span className="turn-label">You</span><div className="user-bubble"><p>{msg.question}</p>{msg.options?.length > 0 && <div className="user-options">{msg.options.map((o,i)=><span key={i}>{o}</span>)}</div>}</div></div>
        ) : msg.thinking ? (
          <div key={msg.id} className="assistant-turn thinking-turn"><span className="twin-avatar" aria-hidden="true"><PenNib size={17}/></span><div className="thinking-content" role="status">{msg.preview && <p className="answer-prose streaming-preview">{msg.preview}</p>}<div><CircleNotch size={16} className="animate-spin"/><span>{msg.preview ? "Writing your answer" : "Thinking through your question"}</span><time>{elapsed}s</time></div><p>{elapsed < 10 ? "Preparing your answer." : "Still waiting for the model response. You can keep drafting below."}</p><span className="thinking-track" aria-hidden="true" /></div></div>
        ) : (
          <div key={msg.id} className="assistant-turn"><span className="twin-avatar" aria-hidden="true"><PenNib size={17}/></span><div className="assistant-content"><AnswerCard msg={msg} onRetry={() => retry(msg)} retrying={retrying || pending} timings={preferences?.timings} speechSupported={canRead} reading={readingId === msg.id} onRead={() => readReply(msg)} speechNotice={speechNotice?.id === msg.id ? speechNotice.text : ""}/></div></div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="chat-composer">
        <label className="sr-only" htmlFor="chat-input">Message</label>
        <div className="composer-entry"><Textarea ref={inputRef} id="chat-input" rows={1} readOnly={listening} value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
          placeholder="Ask anything…" aria-label="Message" />
          <Button variant="ghost" size="icon" className="voice-button" onClick={toggleVoice} aria-pressed={listening}
            aria-label={listening ? "Stop voice typing" : "Start voice typing"} title={speechSupported ? "Voice typing" : "Voice typing requires a compatible browser"}>
            {listening ? <Stop size={19} weight="fill"/> : <Microphone size={21}/>}
          </Button>
          <Button onClick={submit} disabled={pending || listening || !text.trim()} aria-label="Send" className="send-button">
            {pending ? <CircleNotch size={19} className="animate-spin"/> : <PaperPlaneTilt size={19}/>}<span className="sr-only">Send</span>
          </Button>
        </div>
        <div className="voice-options"><label htmlFor="voice-language">Voice</label><select id="voice-language" value={voiceLang} disabled={listening} onChange={e => setVoiceLang(e.target.value)}><option value="hi-IN">Hindi</option><option value="en-IN">English</option></select><span>{listening ? "Listening · tap stop, then review your message" : "Tap mic to dictate"}</span></div>
        {(voiceError || listening) && <p className="voice-status" role="status">{voiceError || "Your browser’s speech service processes audio. Nothing is sent until you press Send."}</p>}
        {showOpts && <div className="chat-choice-input"><div><label htmlFor="chat-options">Choices to weigh</label><button type="button" onClick={() => setOpts("")}>Clear</button></div><Textarea id="chat-options" rows={3} value={opts} onChange={e=>setOpts(e.target.value)} placeholder="One choice per line, or separate with ; or |" aria-label="Choices for the twin to weigh" /></div>}
        <div className="composer-tools"><div className="composer-secondary">
          <Button variant="ghost" size="sm" onClick={() => setShowOpts(v => !v)} aria-expanded={showOpts}><Plus size={16}/><span>Choices</span></Button>
        </div></div>
      </div>
      <p className="composer-footnote">Enter to send · Shift + Enter for a new line</p>
    </div>
  );
}
