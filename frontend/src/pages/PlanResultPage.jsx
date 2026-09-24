import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import Disclaimer from "../components/Disclaimer.jsx";
import Icon from "../components/Icon.jsx";
import { PageLoader } from "../components/Loader.jsx";
import MacroMeters from "../components/MacroMeters.jsx";
import MealCard from "../components/MealCard.jsx";
import PageHeader from "../components/PageHeader.jsx";
import SourceBadge from "../components/SourceBadge.jsx";
import Thali from "../components/Thali.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { deletePlan, downloadPlan, getPlan, savePlanToCloud } from "../services/planService.js";
import { saveBlob } from "../utils/download.js";
import { formatDateTime, formatKcal, formatNumber } from "../utils/format.js";
import { MEAL_SLOTS, optionLabel } from "../utils/options.js";

export default function PlanResultPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [plan, setPlan] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [message, setMessage] = useState(
    location.state?.justCreated ? { tone: "success", text: "Plan generated and saved to your account." } : null,
  );
  const [busy, setBusy] = useState(null);
  useDocumentTitle(plan ? plan.title : "Diet plan");

  useEffect(() => {
    let cancelled = false;
    setPlan(null);
    setLoadError(null);
    getPlan(planId)
      .then((data) => !cancelled && setPlan(data))
      .catch((err) => !cancelled && setLoadError(err));
    return () => {
      cancelled = true;
    };
  }, [planId]);

  async function run(action, task) {
    setBusy(action);
    setMessage(null);
    try {
      await task();
    } catch (err) {
      setMessage({ tone: "error", text: err.message });
    } finally {
      setBusy(null);
    }
  }

  const saveToCloud = (format) =>
    run(`save-${format}`, async () => {
      const file = await savePlanToCloud(plan.id, format);
      setMessage({
        tone: "success",
        text: `Saved to cloud storage as ${file.filename}.`,
        link: { to: "/files", label: "Open Cloud files" },
      });
    });

  const download = (format) =>
    run(`download-${format}`, async () => {
      const { blob, filename } = await downloadPlan(plan.id, format);
      saveBlob(blob, filename ?? `diet-plan.${format}`);
    });

  const remove = () => {
    if (!window.confirm("Delete this plan? This can't be undone.")) return;
    run("delete", async () => {
      await deletePlan(plan.id);
      navigate("/plans", { replace: true, state: { message: "Plan deleted." } });
    });
  };

  if (loadError) {
    return (
      <div className="container page">
        <Alert tone="error" title={loadError.status === 404 ? "Plan not found" : "Couldn't load this plan"}>
          {loadError.status === 404
            ? "It may have been deleted, or it belongs to another account."
            : loadError.message}
        </Alert>
        <Link to="/plans" className="link">
          Back to saved plans
        </Link>
      </div>
    );
  }
  if (!plan) return <PageLoader label="Loading plan" />;

  const { targets, totals } = plan.nutrition_summary;
  const meals = { breakfast: plan.breakfast, lunch: plan.lunch, snack: plan.snack, dinner: plan.dinner };

  return (
    <div className="container page plan">
      <PageHeader eyebrow={`Generated ${formatDateTime(plan.created_at)}`} title={plan.title}>
        <SourceBadge plan={plan} />
      </PageHeader>

      {message && (
        <Alert
          tone={message.tone}
          action={
            message.link && (
              <Link to={message.link.to} className="btn btn--secondary btn--small">
                {message.link.label}
              </Link>
            )
          }
        >
          {message.text}
        </Alert>
      )}

      <section className="card plan__overview" aria-label="Day overview">
        <Thali meals={meals} total={totals.calories} target={targets.calories} />
        <div className="plan__numbers">
          <p className="figure">
            <span className="figure__value">{formatNumber(totals.calories)}</span>
            <span className="figure__unit">kcal planned</span>
          </p>
          <p className="muted">
            Daily target {formatKcal(targets.calories)}: estimated energy use of{" "}
            {formatKcal(targets.tdee)} (resting {formatKcal(targets.bmr)}) adjusted for{" "}
            {optionLabel(plan.goal).toLowerCase()}.
          </p>
          <MacroMeters totals={totals} targets={targets} />
          <p className="plan__fibre">Fibre {totals.fiber_g} g across the day</p>
          <div className="hydration">
            <Icon name="drop" size={20} />
            <p>{plan.hydration_tip}</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="meals-heading">
        <h2 id="meals-heading" className="section__title">
          Meals
        </h2>
        <div className="meals-grid">
          {MEAL_SLOTS.map((slot) => (
            <MealCard key={slot} slot={slot} meal={plan[slot]} />
          ))}
        </div>
      </section>

      <section className="card plan__tips" aria-labelledby="tips-heading">
        <h2 id="tips-heading" className="card__title">
          General tips
        </h2>
        <ul>
          {plan.tips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </section>

      <Disclaimer text={plan.disclaimer} />

      <section className="card plan-actions no-print" aria-labelledby="actions-heading">
        <h2 id="actions-heading" className="card__title">
          Keep this plan
        </h2>
        <div className="plan-actions__groups">
          <div className="plan-actions__group">
            <p className="plan-actions__label">Save a copy to cloud storage</p>
            <button type="button" className="btn btn--primary" onClick={() => saveToCloud("txt")} disabled={Boolean(busy)}>
              <Icon name="cloud" size={18} />
              {busy === "save-txt" ? "Saving…" : "Save as text"}
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => saveToCloud("json")} disabled={Boolean(busy)}>
              <Icon name="cloud" size={18} />
              {busy === "save-json" ? "Saving…" : "Save as JSON"}
            </button>
          </div>
          <div className="plan-actions__group">
            <p className="plan-actions__label">Download to this device</p>
            <button type="button" className="btn btn--secondary" onClick={() => download("txt")} disabled={Boolean(busy)}>
              <Icon name="download" size={18} />
              Text file
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => download("json")} disabled={Boolean(busy)}>
              <Icon name="download" size={18} />
              JSON
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => window.print()}>
              <Icon name="printer" size={18} />
              Print or save as PDF
            </button>
          </div>
          <div className="plan-actions__group">
            <p className="plan-actions__label">Remove</p>
            <button type="button" className="btn btn--ghost btn--danger" onClick={remove} disabled={Boolean(busy)}>
              <Icon name="trash" size={18} />
              {busy === "delete" ? "Deleting…" : "Delete plan"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
