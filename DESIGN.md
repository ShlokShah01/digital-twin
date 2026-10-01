# Digital Twin - Warm Ivory

## Direction

User-selected mockup A: Warm Ivory. An elegant light workspace used for everyday conversation, with cream canvas, ivory navigation, espresso text, bronze actions, and editorial serif branding. Operate mode: clear tasks and familiar controls take priority.

## Reference

Chosen comp: C:/Users/mythi/.codex/generated_images/01a0e773-8b4d-7510-b1b3-6ee6e1b677e6/exec-367f6e24-7914-4a9b-b097-45ed6cd8b9d9.png.

## System

Canvas #faf8f4; surface #fffdfa; sidebar #f0ede6; selected/message surface #f0ece5; ink #292720; secondary #686158; bronze #7b684e; borders #ded7cc. Cormorant Garamond is self-hosted for branding and headings; existing Geist remains the interface face. Subtle 8–10px corners and fine borders. No gradients, glow, dark panels, or decorative charts.

## Composition and behavior

One 216px desktop rail contains New Conversation and existing sessions. Your profile stays at the bottom and opens Overview, Chat, Profile, Knowledge graph, How it works and Rebuild above it. Main chat has one Conversation header, a centered column up to 780px, soft message bubbles, and a compact growing composer with adjacent mic/send controls. Personal reports and metadata stay out of chat.

Below 768px the rail becomes a dismissible drawer with keyboard focus management. Input stays usable at 16px and controls retain accessible targets. Preserve routes, sessions, rename/archive/restore/delete, choice entry, streamed replies, retry and Hindi/English voice dictation. Respect reduced motion. Apply the same ivory palette across all pages; keep backend APIs unchanged.

## Settings

The profile menu includes Settings. Persist preferences in this browser: Warm Ivory (default), Cool Slate, Soft Sage, Evening; standard/larger chat text; interface motion; optional measured reply timing (off by default); optional generic reply-ready notifications only when the tab is hidden and browser permission is granted. Graph community colors can follow the theme or use warm/cool/forest palettes without changing graph data. Resource links and live backend model/device/index status are shown separately from chat. Reset restores preferences and preserves sessions. No credentials are exposed.

## Brand mark

Use the existing Phosphor PenNib icon as a compact digital pen mark in the brand, profile button, mobile header and chat avatars. The user explicitly rejected the leaf motif. Keep consistent bronze strokes and restrained sizing.

## Conversation tools and resources

The rail has compact title/question/answer search. A small Export chat control saves visible turns and choices as Markdown, without internal evidence or metadata. Resources is a profile-menu destination with editorial sections, native troubleshooting disclosures, and official documentation links. It inherits workspace colors and responsive settings-page spacing.

## Spoken replies

Each successful final answer has a compact Read aloud toggle below the text. Playback is opt-in and uses local Pocket TTS on CPU. Settings offers Alba (conversational), Marius, and Anna. Use the official human-evaluated English calibration (temperature 0.3, one decoding step), INT8 quantization and four CPU threads. Keep the generated prosody intact and playback volume at 70%. While generating, show a spinner and Cancel audio; while playing, show Stop reading. Only one reply plays at a time. Starting dictation, changing sessions, and leaving chat cancel playback and release audio URLs. Show speech errors beside the control without affecting chat. The English model reports a clear limitation for Hindi speech; Hindi/English dictation remains independent. Buffer WAV playback to avoid gaps; CPU generation already in progress finishes after cancellation.
