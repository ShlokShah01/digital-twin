import { ArrowUpRight } from "@phosphor-icons/react";

const LINKS = [
  ["Project documentation", "Setup instructions, source code, and contribution history.", "https://github.com/ShlokShah01/digital-twin#readme"],
  ["NVIDIA model reference", "Official documentation for the hosted answer models.", "https://docs.api.nvidia.com/nim/reference/models-1"],
  ["Cloudflare Tunnel guide", "Learn how to connect a local service to a shareable address.", "https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/"],
];
export default function Resources() {
  return <div className="settings-page resources-page">
    <header><h1>Resources</h1><p>A practical guide to your twin, your conversations, and your workspace.</p></header>
    <section aria-labelledby="resources-start"><h2 id="resources-start">Make your twin useful</h2>
      <p>Ask a direct question for a quick answer. Add choices when you want help comparing a decision. Explore your saved knowledge separately from chat.</p>
      <div className="settings-resources"><a href="#/profile">Review your profile<ArrowUpRight size={16}/></a><a href="#/graph">Explore your knowledge graph<ArrowUpRight size={16}/></a><a href="#/how">Understand the twin<ArrowUpRight size={16}/></a></div>
    </section>
    <section aria-labelledby="resources-history"><h2 id="resources-history">Keep useful conversations</h2><p>Search the sidebar by a conversation title, question, or answer. Export chat saves the current conversation as a Markdown file you can read in a text editor.</p><p>History is saved in this browser, on this device. It does not sync between your laptop and phone. Clearing browser storage removes it, so export conversations you want to keep.</p></section>
    <section aria-labelledby="resources-help"><h2 id="resources-help">Troubleshooting</h2>
      <details><summary>The phone cannot open the website</summary><p>Connect both devices to the same Wi-Fi and use the laptop's network address. A localhost or 127.0.0.1 link points to the device opening it. Keep the laptop and backend running; the address can change when the network changes.</p></details>
      <details><summary>An answer takes too long or fails</summary><p>Retry once and check Resources and system in Settings for the configured model and GPU status. Hosted model load and provider request limits can affect response time.</p><a className="settings-link" href="#/settings">Open settings<ArrowUpRight size={16}/></a></details>
      <details><summary>Voice typing is unavailable</summary><p>Use a compatible browser such as Chrome or Edge and allow microphone access. Some browsers require HTTPS for microphone features. You can always type your message instead.</p></details>
      <details><summary>How is my data used?</summary><p>The backend uses saved source material to retrieve relevant context. With a hosted answer model enabled, the question and relevant context are sent to the configured model provider. Exported chats stay on your device unless you share them.</p></details>
    </section>
    <section aria-labelledby="resources-docs"><h2 id="resources-docs">Official references</h2><div className="resource-links">{LINKS.map(([title, note, href]) => <a key={href} href={href} target="_blank" rel="noopener noreferrer"><span><strong>{title}</strong><small>{note}</small></span><ArrowUpRight size={19}/></a>)}</div></section>
  </div>;
}
