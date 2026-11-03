const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, options);

  if (!res.ok) {
    let message = "Something went wrong";
    try {
      const body = await res.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : body.detail?.message ?? message;
    } catch {
      // response had no JSON body, keep the default message
    }
    throw new Error(message);
  }

  if (res.status === 204) return null;

  return res.json();
}

export const listDocuments = () => request("/documents");

export const getDocument = (id) => request(`/documents/${id}`);

export function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/documents", { method: "POST", body: form });
}

export const deleteDocument = (id) =>
  request(`/documents/${id}`, { method: "DELETE" });

export const documentFileUrl = (id, page) =>
  `${API_URL}/documents/${id}/file${page ? `#page=${page}` : ""}`;


export const createConversation = () =>
  request("/conversations", { method: "POST" });

export const listConversations = () => request("/conversations");

export const getMessages = (id) => request(`/conversations/${id}/messages`);

export const askQuestion = (id, question) =>
  request(`/conversations/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

export const deleteConversation = (id) =>
  request(`/conversations/${id}`, { method: "DELETE" });


export const pageImageUrl = (id, page) =>
  `${API_URL}/documents/${id}/pages/${page}/image`;