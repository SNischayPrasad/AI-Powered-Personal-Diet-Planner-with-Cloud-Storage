import { useCallback, useEffect, useState } from "react";
import Alert from "../components/Alert.jsx";
import EmptyState from "../components/EmptyState.jsx";
import FileTile from "../components/FileTile.jsx";
import { Loader } from "../components/Loader.jsx";
import PageHeader from "../components/PageHeader.jsx";
import UploadDropzone from "../components/UploadDropzone.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { deleteFile, downloadFile, listFiles, uploadFile } from "../services/fileService.js";
import { saveBlob } from "../utils/download.js";
import { formatBytes } from "../utils/format.js";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

export default function CloudFilesPage() {
  useDocumentTitle("Cloud files");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await listFiles());
    } catch (err) {
      setError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleFile(file) {
    setError(null);
    setMessage(null);
    const maxMb = data?.max_upload_mb ?? 4;
    // Quick feedback only; the server checks the actual file content either way.
    if (file.type && !ACCEPTED_TYPES.includes(file.type)) {
      setError({ message: "Only JPEG, PNG and WebP images and PDF documents can be uploaded." });
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setError({ message: `That file is ${formatBytes(file.size)}. Files must be ${maxMb} MB or smaller.` });
      return;
    }
    setUploading(true);
    try {
      const stored = await uploadFile(file);
      setMessage(`Uploaded ${stored.filename} to cloud storage.`);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(file) {
    setBusyId(file.id);
    try {
      const { blob, filename } = await downloadFile(file.id);
      saveBlob(blob, filename ?? file.filename);
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(file) {
    if (!window.confirm(`Delete ${file.filename}? This can't be undone.`)) return;
    setBusyId(file.id);
    setMessage(null);
    try {
      await deleteFile(file.id);
      setMessage(`Deleted ${file.filename}.`);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  }

  const usage = data ? Math.min(data.total / data.max_files, 1) : 0;

  return (
    <div className="container page files">
      <PageHeader eyebrow="Object storage" title="Cloud files">
        <p>Meal photos, documents and saved plans. Only you can see them.</p>
      </PageHeader>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error.message}</Alert>}

      <div className="files__top">
        <UploadDropzone onFile={handleFile} disabled={uploading} maxMb={data?.max_upload_mb ?? 4} />
        <section className="card usage" aria-labelledby="usage-heading">
          <h2 id="usage-heading" className="card__title">
            Storage used
          </h2>
          {data ? (
            <>
              <p className="usage__numbers">
                {data.total} of {data.max_files} files · {formatBytes(data.total_bytes)}
              </p>
              <span
                className="meter"
                role="img"
                aria-label={`${data.total} of ${data.max_files} files used`}
              >
                <span className="meter__fill" style={{ width: `${usage * 100}%` }} />
              </span>
            </>
          ) : (
            <Loader label="Loading storage usage" />
          )}
          {uploading && <p className="muted">Uploading…</p>}
        </section>
      </div>

      {data && data.total === 0 && (
        <EmptyState icon="image" title="No files yet">
          Upload a photo of a meal, or open a plan and choose “Save as text” to store a copy here.
        </EmptyState>
      )}

      {data && data.total > 0 && (
        <div className="files-grid">
          {data.items.map((file) => (
            <FileTile
              key={file.id}
              file={file}
              busy={busyId === file.id}
              onDownload={handleDownload}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
