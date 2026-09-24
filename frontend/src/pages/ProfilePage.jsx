import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import { ChipGroup, ChoiceCards, Field } from "../components/FormControls.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { updateProfile } from "../services/profileService.js";
import {
  ACTIVITY_LEVELS,
  ALLERGENS,
  CUISINES,
  DIETARY_PREFERENCES,
  GOALS,
  SEXES,
} from "../utils/options.js";

function fromUser(user) {
  return {
    name: user.name ?? "",
    age: user.age ?? "",
    sex: user.sex ?? "unspecified",
    height_cm: user.height_cm ?? "",
    weight_kg: user.weight_kg ?? "",
    activity_level: user.activity_level ?? "",
    dietary_preference: user.dietary_preference ?? "",
    goal: user.goal ?? "",
    allergies: user.allergies ?? [],
    cuisine_preference: user.cuisine_preference ?? "any",
  };
}

// Mirrors the API's validation so mistakes are caught before the request.
function validate(form) {
  const errors = {};
  if (!form.name.trim()) errors.name = "Enter your name.";
  const range = (key, min, max, what) => {
    const value = Number(form[key]);
    if (form[key] === "" || Number.isNaN(value)) errors[key] = `Enter your ${what}.`;
    else if (value < min || value > max) errors[key] = `Enter a value from ${min} to ${max}.`;
  };
  range("age", 18, 90, "age");
  if (!errors.age && !Number.isInteger(Number(form.age))) errors.age = "Enter a whole number of years.";
  range("height_cm", 100, 250, "height");
  range("weight_kg", 30, 300, "weight");
  if (!form.activity_level) errors.activity_level = "Choose an activity level.";
  if (!form.dietary_preference) errors.dietary_preference = "Choose a dietary preference.";
  if (!form.goal) errors.goal = "Choose a goal.";
  return errors;
}

export default function ProfilePage() {
  useDocumentTitle("Profile");
  const { user, setUser } = useAuth();
  const location = useLocation();
  const [form, setForm] = useState(() => fromUser(user));
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const welcome = Boolean(location.state?.welcome) && !user.profile_complete;

  const set = (field) => (value) => {
    setSaved(false);
    setForm((current) => ({ ...current, [field]: value }));
  };
  const input = (field) => (event) => set(field)(event.target.value);

  async function handleSubmit(event) {
    event.preventDefault();
    const errors = validate(form);
    setFieldErrors(errors);
    setError(null);
    setSaved(false);
    if (Object.keys(errors).length) return;

    setSaving(true);
    try {
      const updated = await updateProfile({
        name: form.name.trim(),
        age: Number(form.age),
        sex: form.sex,
        height_cm: Number(form.height_cm),
        weight_kg: Number(form.weight_kg),
        activity_level: form.activity_level,
        dietary_preference: form.dietary_preference,
        goal: form.goal,
        allergies: form.allergies,
        cuisine_preference: form.cuisine_preference,
      });
      setUser(updated);
      setSaved(true);
    } catch (err) {
      setError(err);
      setFieldErrors(err.fieldErrors ?? {});
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="container page profile">
      <PageHeader eyebrow="Profile" title="Your profile">
        <p>
          Used to estimate your daily energy needs. Enter demo data only, not real health
          information.
        </p>
      </PageHeader>

      {welcome && (
        <Alert tone="info" title="Account created">
          Fill in your profile, then generate your first plan.
        </Alert>
      )}
      {error && <Alert tone="error">{error.message}</Alert>}
      {saved && (
        <Alert
          tone="success"
          title="Profile saved"
          action={
            <Link to="/generate" className="btn btn--primary btn--small">
              Generate a plan
            </Link>
          }
        >
          New plans will use these details.
        </Alert>
      )}

      <form className="profile__form" onSubmit={handleSubmit} noValidate>
        <section className="card form-section" aria-labelledby="about-heading">
          <h2 id="about-heading" className="card__title">
            About you
          </h2>
          <div className="form-grid">
            <Field id="profile-name" label="Name" error={fieldErrors.name}>
              {(props) => <input {...props} autoComplete="name" value={form.name} onChange={input("name")} />}
            </Field>
            <Field id="profile-age" label="Age" hint="18 to 90 years" error={fieldErrors.age}>
              {(props) => (
                <input {...props} type="number" inputMode="numeric" min="18" max="90" value={form.age} onChange={input("age")} />
              )}
            </Field>
            <Field id="profile-sex" label="Sex (for the calorie formula)" error={fieldErrors.sex}>
              {(props) => (
                <select {...props} value={form.sex} onChange={input("sex")}>
                  {SEXES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field id="profile-height" label="Height (cm)" hint="100 to 250 cm" error={fieldErrors.height_cm}>
              {(props) => (
                <input {...props} type="number" inputMode="decimal" min="100" max="250" step="0.5" value={form.height_cm} onChange={input("height_cm")} />
              )}
            </Field>
            <Field id="profile-weight" label="Weight (kg)" hint="30 to 300 kg" error={fieldErrors.weight_kg}>
              {(props) => (
                <input {...props} type="number" inputMode="decimal" min="30" max="300" step="0.1" value={form.weight_kg} onChange={input("weight_kg")} />
              )}
            </Field>
          </div>
        </section>

        <section className="card form-section" aria-labelledby="activity-heading">
          <h2 id="activity-heading" className="card__title">
            Activity
          </h2>
          <ChoiceCards
            name="activity_level"
            legend="How active are you on a typical week?"
            options={ACTIVITY_LEVELS}
            value={form.activity_level}
            onChange={set("activity_level")}
            error={fieldErrors.activity_level}
          />
        </section>

        <section className="card form-section" aria-labelledby="food-heading">
          <h2 id="food-heading" className="card__title">
            Food preferences
          </h2>
          <ChoiceCards
            name="dietary_preference"
            legend="Dietary preference"
            options={DIETARY_PREFERENCES}
            value={form.dietary_preference}
            onChange={set("dietary_preference")}
            error={fieldErrors.dietary_preference}
          />
          <ChoiceCards
            name="goal"
            legend="Goal"
            options={GOALS}
            value={form.goal}
            onChange={set("goal")}
            error={fieldErrors.goal}
          />
          <ChipGroup
            legend="Allergies and foods to avoid"
            hint="Dishes containing these are never suggested."
            options={ALLERGENS}
            values={form.allergies}
            onChange={set("allergies")}
          />
          <Field id="profile-cuisine" label="Preferred cuisine">
            {(props) => (
              <select {...props} value={form.cuisine_preference} onChange={input("cuisine_preference")}>
                {CUISINES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </section>

        <div className="form-actions">
          <button type="submit" className="btn btn--primary btn--large" disabled={saving}>
            {saving ? "Saving…" : "Save profile"}
          </button>
        </div>
      </form>
    </div>
  );
}
