import { useCallback, useEffect, useState } from "react";
import {
  deleteConversation,
  deleteDocument,
  listConversations,
  listDocuments,
} from "./api";
import UploadBox from "./components/UploadBox";
import DocumentList from "./components/DocumentList";
import ChatList from "./components/ChatList";
import ChatPanel from "./components/ChatPanel";

const ACTIVE = ["uploaded", "parsing", "chunking", "describing", "embedding", "storing"];

export default function App() {
  const [docs, setDocs] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [error, setError] = useState("");
  const [activeConversation, setActiveConversation] = useState(null);

  const refresh = useCallback(() => {
    listDocuments()
      .then(setDocs)
      .catch((e) => setError(e.message));
  }, []);

  const refreshConversations = useCallback(() => {
    listConversations()
      .then(setConversations)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    refresh();
    refreshConversations();
  }, [refresh, refreshConversations]);

  const hasActive = docs.some((d) => ACTIVE.includes(d.status));

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, [hasActive, refresh]);

  async function handleDelete(id) {
    setError("");
    try {
      await deleteDocument(id);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleDeleteConversation(id) {
    setError("");
    try {
      await deleteConversation(id);
      if (id === activeConversation) setActiveConversation(null);
      refreshConversations();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="layout">
      <ChatList
        conversations={conversations}
        activeId={activeConversation}
        onSelect={setActiveConversation}
        onDelete={handleDeleteConversation}
        onNew={() => setActiveConversation(null)}
      />

      <main className="main">
        <h2>Your documents</h2>
        <UploadBox onUploaded={refresh} />
        {error && <p className="error">{error}</p>}
        <DocumentList docs={docs} onDelete={handleDelete} />

        <h2>Ask your documents</h2>
        <ChatPanel
          conversationId={activeConversation}
          onConversationChange={setActiveConversation}
          onAnswered={refreshConversations}
        />
      </main>
    </div>
  );
}