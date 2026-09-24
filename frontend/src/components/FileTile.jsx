import { Link } from "react-router-dom";
import { useFilePreview } from "../hooks/useFilePreview.js";
import { formatBytes, formatDate } from "../utils/format.js";
import { FILE_CATEGORY_LABELS } from "../utils/options.js";
import Icon from "./Icon.jsx";

export default function FileTile({ file, onDownload, onDelete, busy = false }) {
  const isImage = file.content_type.startsWith("image/");
  const { url, failed } = useFilePreview(isImage ? file.id : null);

  return (
    <article className="file-tile card">
      <div className="file-tile__preview">
        {isImage && url && <img src={url} alt={`Preview of ${file.filename}`} />}
        {(!isImage || failed) && <Icon name={isImage ? "image" : "file"} size={34} />}
        {isImage && !url && !failed && <span className="file-tile__placeholder" aria-hidden="true" />}
      </div>
      <div className="file-tile__body">
        <p className="file-tile__name" title={file.filename}>
          {file.filename}
        </p>
        <p className="file-tile__meta">
          <span className="tag">{FILE_CATEGORY_LABELS[file.category] ?? file.category}</span>
          <span>{formatBytes(file.size_bytes)}</span>
          <span>{formatDate(file.uploaded_at)}</span>
        </p>
        {file.plan_id && (
          <Link className="file-tile__link" to={`/plans/${file.plan_id}`}>
            Open the plan
          </Link>
        )}
      </div>
      {(onDownload || onDelete) && (
        <div className="file-tile__actions">
          {onDownload && (
            <button type="button" className="btn btn--ghost btn--small" onClick={() => onDownload(file)} disabled={busy}>
              <Icon name="download" size={16} />
              Download
            </button>
          )}
          {onDelete && (
            <button type="button" className="btn btn--ghost btn--small btn--danger" onClick={() => onDelete(file)} disabled={busy}>
              <Icon name="trash" size={16} />
              Delete
            </button>
          )}
        </div>
      )}
    </article>
  );
}
