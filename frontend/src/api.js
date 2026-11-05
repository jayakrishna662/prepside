//This tells your frontend where your backend is running.
// import.meta.env.VITE_API_URL checks whether you configured a backend URL in your environment variables.
// if you configured a backend URL it uses that value else it uses default backend URL on local computer i.e "http://127.0.0.1:8000"

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

// this function sends requests to your backend
// The function combines the backend URL and path, so its a helper function to send requests 
async function request(path, options) {  // path tells the function which backend endpoint to contact. options lets you specify the HTTP method and format
  
  // Send a request to the specified backend endpoint using the given options, wait for the response, and store that response in res.
  const res = await fetch(`${API_URL}${path}`, options); 

  // if backend req fails, try to get useful error message from backend
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

  // 204 means the request succeeded, but the server has no response body to return. so return null.
  if (res.status === 204) return null;

  // If the response isn't 204, then return its json data.
  return res.json();
}

// Fetch all documents uploaded by the user. (GET request)
export const listDocuments = () => request("/documents");

// Fetch one specific document using its ID. (GET request)
export const getDocument = (id) => request(`/documents/${id}`);

// Upload a document from the frontend to the backend. (POST request)
export function uploadDocument(file) {
  const form = new FormData(); // FormData packages the PDF for transmission.
  form.append("file", file);
  return request("/documents", { method: "POST", body: form }); // send uploaded document to backend using FormData.
}
// Sends a Request to Delete a specific document(DELETE request)
export const deleteDocument = (id) =>
  request(`/documents/${id}`, { method: "DELETE" });

// construct a URL that lets the frontend open a PDF at a particular page.
export const documentFileUrl = (id, page) =>
  `${API_URL}/documents/${id}/file${page ? `#page=${page}` : ""}`;

// send a request to Create a new chat conversation. (POST request)
export const createConversation = () =>
  request("/conversations", { method: "POST" });

// send a request to Fetch the user's existing conversations. (GET request)
export const listConversations = () => request("/conversations");

// send a request to retrieve all messages belonging to a specific conversation
export const getMessages = (id) => request(`/conversations/${id}/messages`);

// sends the user's question to the backend
// id -> The ID of the conversation where the question is being asked.
// question -> The actual question typed by the user.
export const askQuestion = (id, question) =>
  request(`/conversations/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });


// sends a request to Delete a specific chat conversation
export const deleteConversation = (id) =>
  request(`/conversations/${id}`, { method: "DELETE" });

// Construct a URL for retrieving an image of a specific PDF page.
export const pageImageUrl = (id, page) =>
  `${API_URL}/documents/${id}/pages/${page}/image`;