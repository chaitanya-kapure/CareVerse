import { useEffect, useState } from "react";

import Alert from "./ui/Alert";
import Button from "./ui/Button";
import { getErrorMessage } from "../services/api";

interface DocumentFileActionsProps {
  /**
   * Fetches the stored PDF as bytes.
   *
   * Passed in rather than derived from a document id, because the two callers
   * live behind different authorization boundaries: the patient fetches from
   * `/patients/me/documents/...`, the doctor from
   * `/doctor/patients/{id}/documents/...`. The object-URL and popup dance below
   * is identical either way, so only this function differs.
   */
  fetchOriginal: () => Promise<Blob>;
  /** Name suggested when saving, from the record's own stored filename. */
  filename: string;
}

/**
 * "View original" and "Download" for a stored PDF.
 *
 * Shared so there is one implementation of the two things that are easy to get
 * wrong in a medical-record viewer: the blob is fetched with the bearer token
 * rather than linked (a plain `<a>` cannot authenticate and would 401), and
 * the object URL is revoked when the screen goes away, because object URLs
 * are a browser resource the garbage collector does not reclaim -- a leaked
 * one keeps the bytes of a patient's document alive in the tab indefinitely.
 */
export default function DocumentFileActions({
  fetchOriginal,
  filename,
}: DocumentFileActionsProps) {
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl);
    };
  }, [originalUrl]);

  // Cached for the life of the screen: viewing then downloading a 15 MB
  // discharge summary should not pull it across the network twice.
  const loadOriginal = async (): Promise<string> => {
    if (originalUrl) return originalUrl;
    setIsFetching(true);
    try {
      const blob = await fetchOriginal();
      const url = URL.createObjectURL(blob);
      setOriginalUrl(url);
      return url;
    } finally {
      setIsFetching(false);
    }
  };

  const openOriginal = async () => {
    setFileError(null);
    // Opened synchronously so this still counts as the user's gesture. A tab
    // opened after the `await` would be swallowed by the popup blocker.
    const tab = window.open("", "_blank");
    try {
      const url = await loadOriginal();
      if (tab) {
        tab.location.href = url;
        tab.focus();
      } else {
        setFileError("Your browser blocked the new tab. Use Download instead.");
      }
    } catch (requestError) {
      if (tab) tab.close();
      setFileError(
        getErrorMessage(requestError, "The original document could not be opened."),
      );
    }
  };

  const downloadOriginal = async () => {
    setFileError(null);
    try {
      const url = await loadOriginal();
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
    } catch (requestError) {
      setFileError(
        getErrorMessage(requestError, "The document could not be downloaded."),
      );
    }
  };

  return (
    <>
      <Button variant="secondary" size="sm" onClick={openOriginal} isLoading={isFetching}>
        View original PDF
      </Button>
      <Button variant="secondary" size="sm" onClick={downloadOriginal} isLoading={isFetching}>
        Download
      </Button>
      {fileError && (
        <Alert tone="danger" title="The original file is unavailable" className="w-full">
          {fileError}
        </Alert>
      )}
    </>
  );
}
