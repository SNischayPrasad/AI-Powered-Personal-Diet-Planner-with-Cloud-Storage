import { useState } from "react";
import { Link } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import { Field } from "../components/FormControls.jsx";
import ThaliMark from "../components/ThaliMark.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";

function validate({ name, email, password }) {
  const errors = {};
  if (!name.trim()) errors.name = "Enter your name.";
  if (!/^\S+@\S+\.\S+$/.test(email.trim())) errors.email = "Enter a valid email address.";
  if (password.length < 8) errors.password = "Use at least 8 characters.";
  else if (!/[A-Za-z]/.test(password) || !/\d/.test(password))
    errors.password = "Include at least one letter and one number.";
  else if (new TextEncoder().encode(password).length > 72) errors.password = "Use at most 72 characters.";
  return errors;
}

export default function RegisterPage() {
  useDocumentTitle("Create account");
  const { register } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  async function handleSubmit(event) {
    event.preventDefault();
    const errors = validate(form);
    setFieldErrors(errors);
    setError(null);
    if (Object.keys(errors).length) return;

    setSubmitting(true);
    try {
      // New accounts go straight to the profile form (the route guard performs the redirect).
      await register(
        { ...form, name: form.name.trim(), email: form.email.trim() },
        { redirectTo: { to: "/profile", state: { welcome: true } } },
      );
    } catch (err) {
      setError(err);
      setFieldErrors(err.fieldErrors ?? {});
      setSubmitting(false);
    }
  }

  return (
    <div className="auth container">
      <div className="auth__card card">
        <ThaliMark size={44} />
        <h1 className="auth__title">Create your account</h1>
        <p className="auth__lead">Use made-up demo details. This is an educational project.</p>

        {error && <Alert tone="error">{error.message}</Alert>}

        <form className="form" onSubmit={handleSubmit} noValidate>
          <Field id="register-name" label="Name" error={fieldErrors.name}>
            {(props) => <input {...props} autoComplete="name" value={form.name} onChange={update("name")} />}
          </Field>
          <Field id="register-email" label="Email" error={fieldErrors.email}>
            {(props) => (
              <input {...props} type="email" autoComplete="email" value={form.email} onChange={update("email")} />
            )}
          </Field>
          <Field
            id="register-password"
            label="Password"
            hint="At least 8 characters, with a letter and a number."
            error={fieldErrors.password}
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={update("password")}
              />
            )}
          </Field>
          <button type="submit" className="btn btn--primary btn--block" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth__switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
