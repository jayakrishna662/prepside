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

// document-processing statuses.
const ACTIVE = ["uploaded", "parsing", "chunking", "describing", "embedding", "storing"];

export default function App() {
  // Stores the list of uploaded documents and their current statuses.
  const [docs, setDocs] = useState([]);
  // Stores the list of chat conversations.
  const [conversations, setConversations] = useState([]);
  // Stores an error message to display if an API request fails.
  const [error, setError] = useState("");
  // Stores the ID of the currently selected conversation.
  // null means no conversation is currently selected.
  const [activeConversation, setActiveConversation] = useState(null);

  // Create a function to fetch the latest document list from the backend.
  const refresh = useCallback(() => {
    listDocuments()  // returns the list of documents along with their details, including their current processing status. (this function is defined in src/api.js)
      .then(setDocs) // If successful, updates the docs state with the returned data.
      .catch((e) => setError(e.message)); // If it fails, stores the error message.
  }, []);

  // Create a function to fetch the latest chat conversations.
  const refreshConversations = useCallback(() => {
    listConversations() // Requests conversations from the backend API.
      .then(setConversations) // Updates the conversations state with the returned data.
      .catch((e) => setError(e.message));  // Stores the error message if the request fails.
  }, []);

  // When application is opened, this calls the both functions to display documents list and converstaions
  useEffect(() => {
    refresh();
    refreshConversations();
  }, [refresh, refreshConversations]);

  // checks whether any document is still being processed.
  // hasActive = true: At least one document is still processing, so polling is needed to check for status updates.
  // hasActive = false: No documents are processing, so polling isn't needed.
  // we use hasActive to decide whether frontend should keep polling the backend for document status updates or not.
  const hasActive = docs.some((d) => ACTIVE.includes(d.status));

  useEffect(() => {
    if (!hasActive) return;  // Stop if no documents are processing
    const timer = setInterval(refresh, 2500); // Fetch documents every 2.5 seconds
    return () => clearInterval(timer);  // Stop polling when the effect is cleaned up
  }, [hasActive, refresh]);

  // this function handles deleting a document 
  async function handleDelete(id) {
    setError(""); // Clear any previous error message that occurred due to previous request fails
                  // then attempt new deletion operation
    try {
      await deleteDocument(id); // Send a delete request to the backend
      refresh(); // Fetch the updated document list
    } catch (e) {
      setError(e.message); // Display an error if deletion fails
    }
  }

  //this function handles deleting a chat conversation.
  async function handleDeleteConversation(id) {
    setError("");  // Clear any previous error message
    try {
      await deleteConversation(id); // Ask the backend to delete the conversation
      if (id === activeConversation) setActiveConversation(null); // If the deleted conversation is currently open, it 
      // clears the selection.
      refreshConversations(); // Fetch the updated conversation list
    } catch (e) {
      setError(e.message);  // Display an error if deletion fails
    }
  }


  // this return defines the layout of your application and 
  // connects the data and functions to the UI components.
  return (
    <div className="layout">
      <ChatList
        conversations={conversations} // Displays the list of conversations.
        activeId={activeConversation} // Tells ChatList which conversation is currently selected.
        onSelect={setActiveConversation} // Runs when you select a conversation and updates the active conversation.
        onDelete={handleDeleteConversation} // Runs when you click delete and handles deleting that conversation.
        onNew={() => setActiveConversation(null)} // Clears the current selection to start a new chat.
      />

      <main className="main">
        <h2>Your documents</h2>
        <UploadBox onUploaded={refresh} // displays the PDF upload component and refreshes the document list after upload.
         /> 
        {error && <p className="error">{error}</p> // displays an error message if anything fails
        }
        <DocumentList docs={docs} onDelete={handleDelete} // displays the uploaded documents and allows users to delete them.
         />


        <h2>Ask your documents</h2>
        <ChatPanel   // current chat window
          conversationId={activeConversation}  // displays the selected chat in the conversation list
          onConversationChange={setActiveConversation} // create new conversation when clicked new chat  ChatPanel uses this to tell App “the active chat is now this new one,” so the app and the left list stay in sync.
          onAnswered={refreshConversations} //Refreshes the conversation list after an answer, so the list can show the latest conversation data.
        />
      </main>
    </div>
  );
}