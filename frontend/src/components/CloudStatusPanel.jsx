import { useEffect, useState } from "react";
import { getReadiness, getSystemStatus } from "../services/systemService.js";
import Icon from "./Icon.jsx";

const DESCRIPTIONS = {
  database: {
    sqlite: "SQLite file (local simulation)",
    postgresql: "PostgreSQL (managed cloud database)",
  },
  storage: {
    local: "Simulated bucket on disk",
    s3: "S3-compatible object storage",
  },
};

const AI_NAMES = { anthropic: "Claude API", openai_compatible: "OpenAI-compatible API" };

function describeAi(status) {
  if (status.ai_provider === "rule_based") return "Rule-based engine";
  const name = AI_NAMES[status.ai_provider] ?? status.ai_provider;
  return status.ai_available
    ? `${name} (${status.ai_model}) with rule-based fallback`
    : `${name} not configured; using the rule-based engine`;
}

function StatusRow({ icon, label, detail, state }) {
  return (
    <li className="status-row">
      <Icon name={icon} size={18} className="status-row__icon" />
      <span className="status-row__label">{label}</span>
      <span className="status-row__detail">{detail}</span>
      {state && (
        <span className={`status-pill status-pill--${state === "ok" ? "ok" : "down"}`}>
          <Icon name={state === "ok" ? "check" : "alert"} size={14} />
          {state === "ok" ? "Ready" : "Unavailable"}
        </span>
      )}
    </li>
  );
}

// Live view of which cloud services this deployment is wired to, and whether they respond.
export default function CloudStatusPanel({ title = "Cloud services" }) {
  const [status, setStatus] = useState(null);
  const [ready, setReady] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSystemStatus(), getReadiness()])
      .then(([system, readiness]) => {
        if (cancelled) return;
        setStatus(system);
        setReady(readiness);
      })
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="status-panel card" aria-label={title}>
      <h2 className="card__title">{title}</h2>
      {error && <p className="muted">The API is not reachable right now.</p>}
      {!error && !status && <p className="muted">Checking…</p>}
      {status && (
        <ul className="status-list">
          <StatusRow
            icon="database"
            label="Database"
            detail={DESCRIPTIONS.database[status.database_provider] ?? status.database_provider}
            state={ready?.checks?.database}
          />
          <StatusRow
            icon="bucket"
            label="File storage"
            detail={DESCRIPTIONS.storage[status.storage_provider] ?? status.storage_provider}
            state={ready?.checks?.storage}
          />
          <StatusRow
            icon="sparkle"
            label="Diet planner"
            detail={describeAi(status)}
          />
        </ul>
      )}
    </section>
  );
}
