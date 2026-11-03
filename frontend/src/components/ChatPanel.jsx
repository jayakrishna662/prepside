import { useEffect, useRef, useState } from "react";
import {
  askQuestion,
  createConversation,
  documentFileUrl,
  getMessages,
  pageImageUrl,
} from "../api";

export default function ChatPanel({ conversationId, onConversationChange , onAnswered}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);
  const activeRef = useRef(conversationId);
  const justCreated = useRef(null);

  useEffect(() => {
    activeRef.current = conversationId;
    setError("");

    if (!conversationId) {
      setMessages([]);
      return;
    }
    // A chat we just created has nothing to load yet
    if (justCreated.current === conversationId) {
      justCreated.current = null;
      return;
    }
    getMessages(conversationId)
      .then(setMessages)
      .catch((e) => setError(e.message));
  }, [conversationId]);

  useEffect(() => {
    if (messages.length === 0 && !sending) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  
  async function send() {
    const question = input.trim();
    if (!question || sending) return;

    setError("");
    setSending(true);
    setInput("");
    setMessages((m) => [
      ...m,
      { id: `tmp-${Date.now()}`, role: "user", content: question },
    ]);

    try {
      let id = conversationId;
      if (!id) {
        const conv = await createConversation();
        id = conv.id;
        justCreated.current = id;
        activeRef.current = id;
        onConversationChange(id);
      }
      
      const reply = await askQuestion(id, question);
      if (activeRef.current === id) {
        setMessages((m) => [...m, reply]);
      }
      onAnswered?.();
    } catch (e) {
      setError(e.message);
      setInput(question);
      setMessages((m) => m.slice(0, -1));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat">
      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="muted">Ask a question about your documents.</p>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className={`bubble ${m.found === false ? "notfound" : ""}`}>
              {m.content}
            </div>
            {m.role === "assistant" && m.citations?.length > 0 && (
              <>
                <div className="citations">
                  {m.citations.map((c) => (
                    <a
                      key={`${c.document_id}-${c.page}`}
                      className="cite"
                      href={documentFileUrl(c.document_id, c.page)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {c.filename} · p.{c.page}
                    </a>
                  ))}
                </div>
                <div className="thumbs">
                  {m.citations
                    .filter((c) => c.has_image)
                    .map((c) => (
                      <a
                        key={`thumb-${c.document_id}-${c.page}`}
                        href={documentFileUrl(c.document_id, c.page)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <img
                          className="thumb"
                          src={pageImageUrl(c.document_id, c.page)}
                          alt={`Page ${c.page} of ${c.filename}`}
                          loading="lazy"
                        />
                      </a>
                    ))}
                </div>
              </>
            )}
          </div>
        ))}

        {sending && (
          <div className="msg assistant">
            <div className="bubble muted">Thinking...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="error">{error}</p>}

      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your documents..."
          maxLength={1000}
          disabled={sending}
        />
        <button onClick={send} disabled={sending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}