import { useEffect, useState } from "react";
import { downloadFile } from "../services/fileService.js";

// Private files need the Authorization header, so an <img src="/api/files/..."> would be
// rejected. Instead the image is fetched as a blob and shown through a temporary object URL,
// which is released when the component unmounts.
export function useFilePreview(fileId) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!fileId) return undefined;
    let objectUrl = null;
    let cancelled = false;
    setFailed(false);
    downloadFile(fileId)
      .then(({ blob }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId]);

  return { url, failed };
}
