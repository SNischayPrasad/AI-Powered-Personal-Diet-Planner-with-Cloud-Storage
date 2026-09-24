import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import { Field } from "../components/FormControls.jsx";
import ThaliMark from "../components/ThaliMark.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";

export default function LoginPage() {
  useDocumentTitle("Log in");
  const { login, notice, clearNotice } = useAuth();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    clearNotice();
    setSubmitting(true);
    try {
      // The route guard sends us on once the session starts.
      await login(form, { redirectTo: { to: location.state?.from?.pathname ?? "/dashboard" } });
    } catch (err) {
      setError(err);
      setSubmitting(false);
    }
  }

  return (
    <div className="auth container">
      <div className="auth__card card">
        <ThaliMark size={44} />
        <h1 className="auth__title">Log in</h1>
        <p className="auth__lead">Your plans and files are waiting in your cloud account.</p>

        {notice && !error && <Alert tone="info">{notice}</Alert>}
        {error && <Alert tone="error">{error.message}</Alert>}

        <form className="form" onSubmit={handleSubmit} noValidate>
          <Field id="login-email" label="Email">
            {(props) => (
              <input {...props} type="email" autoComplete="email" required value={form.email} onChange={update("email")} />
            )}
          </Field>
          <Field id="login-password" label="Password">
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="current-password"
                required
                value={form.password}
                onChange={update("password")}
              />
            )}
          </Field>
          <button type="submit" className="btn btn--primary btn--block" disabled={submitting}>
            {submitting ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="auth__switch">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  );
}
