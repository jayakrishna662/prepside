import { documentFileUrl } from "../api";

const LABELS = {
  uploaded: "Uploaded",
  parsing: "Reading PDF",
  chunking: "Splitting text",
  describing: "Describing pictures",
  embedding: "Creating embeddings",
  storing: "Saving",
  ready: "Ready",
  failed: "Failed",
};

const ACTIVE = ["uploaded", "parsing", "chunking", "describing", "embedding", "storing"];

export default function DocumentList({ docs, onDelete }) {
  if (docs.length === 0) {
    return <p className="muted">No documents yet. Upload a PDF to start.</p>;
  }

  function confirmDelete(d) {
    if (window.confirm(`Delete "${d.filename}"? This cannot be undone.`)) {
      onDelete(d.id);
    }
  }

  return (
    <ul className="doc-list">
      {docs.map((d) => (
        <li key={d.id} className="doc-row">
          <div>
            <strong>{d.filename}</strong>
            {d.page_count ? (
              <span className="muted"> · {d.page_count} pages</span>
            ) : null}
            {d.status === "failed" && (
              <div className="error">{d.error_message}</div>
            )}
          </div>
          <div className="row-actions">
            <span className={`badge ${d.status}`}>
              {LABELS[d.status] ?? d.status}
              {(d.status === "embedding" || d.status === "describing") && d.chunks_total > 0
                ? ` ${d.chunks_done}/${d.chunks_total}`
                : ""}
            </span>
            <a
              className="btn-link"
              href={documentFileUrl(d.id)}
              target="_blank"
              rel="noopener noreferrer"
            >
              View
            </a>
            <button
              className="danger"
              disabled={ACTIVE.includes(d.status)}
              onClick={() => confirmDelete(d)}
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}