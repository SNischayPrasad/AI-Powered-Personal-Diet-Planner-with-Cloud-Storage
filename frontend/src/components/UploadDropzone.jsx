import { useRef, useState } from "react";
import Icon from "./Icon.jsx";

const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";

// Drag-and-drop or click-to-choose. The server re-validates every file by its content,
// so this is only a convenience, never the security boundary.
export default function UploadDropzone({ onFile, disabled = false, maxMb = 4 }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file && !disabled) onFile(file);
  };

  return (
    <div
      className={`dropzone${dragging ? " is-dragging" : ""}${disabled ? " is-disabled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        handleFiles(event.dataTransfer.files);
      }}
    >
      <Icon name="upload" size={28} className="dropzone__icon" />
      <p className="dropzone__title">Drop a meal photo or PDF here</p>
      <p className="dropzone__hint">JPEG, PNG, WebP or PDF, up to {maxMb} MB</p>
      <button
        type="button"
        className="btn btn--secondary"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
      >
        Choose a file
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
