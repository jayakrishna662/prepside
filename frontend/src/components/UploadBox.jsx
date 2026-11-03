import { useRef, useState } from "react";
import { uploadDocument } from "../api";

const MAX_FILES = 10;

export default function UploadBox({ onUploaded }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState("");
  const [errors, setErrors] = useState([]);

  async function handleChange(e) {
    const all = Array.from(e.target.files);
    const files = all.slice(0, MAX_FILES);
    if (files.length === 0) return;

    const skipped = all.length - files.length;
    setErrors(
      skipped > 0
        ? [`Only the first ${MAX_FILES} files were uploaded. ${skipped} skipped.`]
        : []
    );
    setUploading(true);

    const failed = [];
    for (let i = 0; i < files.length; i++) {
      setProgress(`Uploading ${i + 1} of ${files.length}...`);
      try {
        await uploadDocument(files[i]);
        onUploaded();
      } catch (err) {
        failed.push(`${files[i].name}: ${err.message}`);
      }
    }

    setErrors((prev) => [...prev, ...failed]);
    setUploading(false);
    setProgress("");
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        onChange={handleChange}
        hidden
      />
      <button onClick={() => inputRef.current.click()} disabled={uploading}>
        {uploading ? progress : "Upload PDFs"}
      </button>
      {errors.map((msg, i) => (
        <p key={i} className="error">
          {msg}
        </p>
      ))}
    </div>
  );
}