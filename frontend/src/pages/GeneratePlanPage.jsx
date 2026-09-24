import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import { ChipGroup, ChoiceCards, Field } from "../components/FormControls.jsx";
import Icon from "../components/Icon.jsx";
import PageHeader from "../components/PageHeader.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { generatePlan } from "../services/planService.js";
import { ALLERGENS, CUISINES, DIETARY_PREFERENCES, GOALS, optionLabel } from "../utils/options.js";

export default function GeneratePlanPage() {
  useDocumentTitle("Generate a plan");
  const { user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(() => ({
    dietary_preference: user.dietary_preference ?? "vegetarian",
    goal: user.goal ?? "balanced",
    allergies: user.allergies ?? [],
    cuisine_preference: user.cuisine_preference ?? "any",
  }));
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);

  const set = (field) => (value) => setForm((current) => ({ ...current, [field]: value }));

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setGenerating(true);
    try {
      const plan = await generatePlan(form);
      navigate(`/plans/${plan.id}`, { state: { justCreated: true } });
    } catch (err) {
      setError(err);
      setGenerating(false);
    }
  }

  return (
    <div className="container page generate">
      <PageHeader eyebrow="New plan" title="Generate a plan">
        <p>Starts from your saved profile. Changes here apply to this plan only.</p>
      </PageHeader>

      {!user.profile_complete && (
        <Alert
          tone="warning"
          title="Your profile is incomplete"
          action={
            <Link to="/profile" className="btn btn--secondary btn--small">
              Complete profile
            </Link>
          }
        >
          Age, height, weight, activity level, diet and goal are needed to estimate your calories.
        </Alert>
      )}
      {error && (
        <Alert tone="error" title={error.code === "no_suitable_meals" ? "No matching dishes" : "Couldn't generate a plan"}>
          {error.message}
        </Alert>
      )}

      <div className="generate__grid">
        <form className="card form-section" onSubmit={handleSubmit}>
          <ChoiceCards
            name="dietary_preference"
            legend="Dietary preference"
            options={DIETARY_PREFERENCES}
            value={form.dietary_preference}
            onChange={set("dietary_preference")}
          />
          <ChoiceCards name="goal" legend="Goal" options={GOALS} value={form.goal} onChange={set("goal")} />
          <ChipGroup
            legend="Allergies and foods to avoid"
            hint="Dishes containing these are never suggested."
            options={ALLERGENS}
            values={form.allergies}
            onChange={set("allergies")}
          />
          <Field id="generate-cuisine" label="Cuisine">
            {(props) => (
              <select
                {...props}
                value={form.cuisine_preference}
                onChange={(event) => set("cuisine_preference")(event.target.value)}
              >
                {CUISINES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <div className="form-actions">
            <button
              type="submit"
              className="btn btn--primary btn--large"
              disabled={generating || !user.profile_complete}
            >
              <Icon name="sparkle" size={18} />
              {generating ? "Generating your plan…" : "Generate plan"}
            </button>
          </div>
        </form>

        <aside className="card generate__profile" aria-labelledby="basis-heading">
          <h2 id="basis-heading" className="card__title">
            Calculated from your profile
          </h2>
          <dl className="summary-list">
            <div>
              <dt>Age</dt>
              <dd>{user.age ?? "—"}</dd>
            </div>
            <div>
              <dt>Sex</dt>
              <dd>{user.sex ? optionLabel(user.sex) : "—"}</dd>
            </div>
            <div>
              <dt>Height</dt>
              <dd>{user.height_cm ? `${user.height_cm} cm` : "—"}</dd>
            </div>
            <div>
              <dt>Weight</dt>
              <dd>{user.weight_kg ? `${user.weight_kg} kg` : "—"}</dd>
            </div>
            <div>
              <dt>Activity</dt>
              <dd>{user.activity_level ? optionLabel(user.activity_level) : "—"}</dd>
            </div>
          </dl>
          <p className="muted small">
            Your daily calorie target is estimated with the Mifflin-St Jeor equation and your
            activity level, then adjusted for the goal you pick.
          </p>
          <Link to="/profile" className="link">
            Edit profile
          </Link>
        </aside>
      </div>
    </div>
  );
}
