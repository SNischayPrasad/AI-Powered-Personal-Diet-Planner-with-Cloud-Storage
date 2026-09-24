import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";

export default function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <div className="container page">
      <EmptyState
        icon="alert"
        title="This page doesn't exist"
        action={
          <Link to="/" className="btn btn--primary">
            Go to the home page
          </Link>
        }
      >
        Check the address, or head back to the start.
      </EmptyState>
    </div>
  );
}
