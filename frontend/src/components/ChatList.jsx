export default function ChatList({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onNew,
}) {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">PREPSIDE</div>
      <button className="new-chat" onClick={onNew}>
        + New chat
      </button>

      <div className="sidebar-label">Chats</div>
      {conversations.length === 0 && (
        <p className="muted small">No chats yet.</p>
      )}

      <ul className="chat-list">
        {conversations.map((c) => (
          <li
            key={c.id}
            className={`chat-item ${c.id === activeId ? "active" : ""}`}
          >
            <button
              className="chat-title"
              onClick={() => onSelect(c.id)}
              title={c.title}
            >
              {c.title}
            </button>
            <button
              className="chat-delete"
              title="Delete chat"
              onClick={() => {
                if (window.confirm(`Delete "${c.title}"?`)) onDelete(c.id);
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}