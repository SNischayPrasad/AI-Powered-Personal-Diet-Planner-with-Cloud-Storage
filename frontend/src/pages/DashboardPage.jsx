import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import CloudStatusPanel from "../components/CloudStatusPanel.jsx";
import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";
import { Loader } from "../components/Loader.jsx";
import MacroMeters from "../components/MacroMeters.jsx";
import PageHeader from "../components/PageHeader.jsx";
import SourceBadge from "../components/SourceBadge.jsx";
import Thali from "../components/Thali.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { listFiles } from "../services/fileService.js";
import { getPlan, listPlans } from "../services/planService.js";
import { formatBytes, formatDate, formatDateTime, formatKcal } from "../utils/format.js";
import { optionLabel } from "../utils/options.js";

function mealsOf(plan) {
  return { breakfast: plan.breakfast, lunch: plan.lunch, snack: plan.snack, dinner: plan.dinner };
}

export default function DashboardPage() {
  useDocumentTitle("Dashboard");
  const { user, refreshUser, logout } = useAuth();
  const [plans, setPlans] = useState(null);
  const [latest, setLatest] = useState(null);
  const [files, setFiles] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    refreshUser().catch(() => {});
    (async () => {
      try {
        const [planList, fileList] = await Promise.all([listPlans({ limit: 6 }), listFiles()]);
        if (cancelled) return;
        setPlans(planList);
        setFiles(fileList);
        if (planList.items.length) {
          const detail = await getPlan(planList.items[0].id);
          if (!cancelled) setLatest(detail);
        }
      } catch (err) {
        if (!cancelled) setError(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  const firstName = user?.name?.split(" ")[0] || "there";
  const previous = plans?.items.slice(1) ?? [];

  return (
    <div className="container page dashboard">
      <PageHeader
        eyebrow={formatDate(new Date().toISOString())}
        title={`Welcome, ${firstName}`}
        actions={
          <Link to="/generate" className="btn btn--primary">
            <Icon name="plus" size={18} />
            Generate new plan
          </Link>
        }
      >
        <ul className="facts">
          <li>
            <span className="facts__label">Current goal</span>
            {user.goal ? optionLabel(user.goal) : "Not set"}
          </li>
          <li>
            <span className="facts__label">Diet preference</span>
            {user.dietary_preference ? optionLabel(user.dietary_preference) : "Not set"}
          </li>
          <li>
            <span className="facts__label">Allergies</span>
            {user.allergies.length ? user.allergies.map(optionLabel).join(", ") : "None listed"}
          </li>
        </ul>
      </PageHeader>

      {!user.profile_complete && (
        <Alert
          tone="warning"
          title="Finish your profile to start planning"
          action={
            <Link to="/profile" className="btn btn--secondary btn--small">
              Complete profile
            </Link>
          }
        >
          The planner needs your age, height, weight, activity level, diet and goal.
        </Alert>
      )}
      {error && <Alert tone="error">{error.message}</Alert>}

      <div className="dashboard__grid">
        <div className="dashboard__main">
          <section className="card latest" aria-labelledby="latest-heading">
            <div className="card__head">
              <h2 id="latest-heading" className="card__title">
                Latest plan
              </h2>
              {latest && <SourceBadge plan={latest} compact />}
            </div>
            {plans === null && !error && <Loader label="Loading your plans" />}
            {plans && plans.items.length === 0 && (
              <EmptyState
                icon="sparkle"
                title="No plans yet"
                action={
                  user.profile_complete ? (
                    <Link to="/generate" className="btn btn--primary">
                      Generate your first plan
                    </Link>
                  ) : (
                    <Link to="/profile" className="btn btn--primary">
                      Complete your profile
                    </Link>
                  )
                }
              >
                Your first plan takes a few seconds and is saved to your account automatically.
              </EmptyState>
            )}
            {latest && (
              <div className="latest__body">
                <Thali
                  meals={mealsOf(latest)}
                  total={latest.nutrition_summary.totals.calories}
                  target={latest.calorie_target}
                />
                <div className="latest__side">
                  <p className="latest__title">{latest.title}</p>
                  <p className="muted">Generated {formatDateTime(latest.created_at)}</p>
                  <MacroMeters totals={latest.nutrition_summary.totals} targets={latest.nutrition_summary.targets} />
                  <Link to={`/plans/${latest.id}`} className="btn btn--secondary">
                    View full plan
                    <Icon name="arrowRight" size={16} />
                  </Link>
                </div>
              </div>
            )}
          </section>

          <section className="card" aria-labelledby="previous-heading">
            <div className="card__head">
              <h2 id="previous-heading" className="card__title">
                Previous plans
              </h2>
              {plans?.total > 0 && (
                <Link to="/plans" className="link">
                  See all {plans.total}
                </Link>
              )}
            </div>
            {previous.length ? (
              <ul className="plan-list">
                {previous.map((plan) => (
                  <li key={plan.id}>
                    <Link to={`/plans/${plan.id}`} className="plan-list__item">
                      <span className="plan-list__title">{plan.title}</span>
                      <span className="plan-list__meta">
                        {formatDate(plan.created_at)} · {formatKcal(plan.total_calories)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Older plans will appear here.</p>
            )}
          </section>
        </div>

        <aside className="dashboard__side">
          <section className="card" aria-labelledby="profile-heading">
            <div className="card__head">
              <h2 id="profile-heading" className="card__title">
                Your profile
              </h2>
              <Link to="/profile" className="link">
                Edit
              </Link>
            </div>
            <dl className="summary-list">
              <div>
                <dt>Age</dt>
                <dd>{user.age ?? "—"}</dd>
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
              <div>
                <dt>Cuisine</dt>
                <dd>{optionLabel(user.cuisine_preference)}</dd>
              </div>
            </dl>
          </section>

          <section className="card" aria-labelledby="files-heading">
            <div className="card__head">
              <h2 id="files-heading" className="card__title">
                Uploaded files
              </h2>
              <Link to="/files" className="link">
                Manage
              </Link>
            </div>
            {files === null && !error && <Loader label="Loading files" />}
            {files && files.total === 0 && (
              <p className="muted">No files yet. Upload meal photos or save a plan to cloud storage.</p>
            )}
            {files && files.total > 0 && (
              <>
                <p className="muted">
                  {files.total} {files.total === 1 ? "file" : "files"} · {formatBytes(files.total_bytes)}
                </p>
                <ul className="mini-files">
                  {files.items.slice(0, 4).map((file) => (
                    <li key={file.id}>
                      <Icon name={file.content_type.startsWith("image/") ? "image" : "file"} size={16} />
                      <span>{file.filename}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <CloudStatusPanel />

          <button type="button" className="btn btn--ghost btn--block" onClick={logout}>
            <Icon name="logout" size={16} />
            Log out
          </button>
        </aside>
      </div>
    </div>
  );
}
