import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Alert from "../components/Alert.jsx";
import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";
import { Loader } from "../components/Loader.jsx";
import PageHeader from "../components/PageHeader.jsx";
import SourceBadge from "../components/SourceBadge.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { deletePlan, listPlans } from "../services/planService.js";
import { formatDateTime, formatKcal } from "../utils/format.js";

const PAGE_SIZE = 10;

export default function SavedPlansPage() {
  useDocumentTitle("Saved plans");
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(location.state?.message ?? null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async (offset) => {
    setLoading(true);
    setError(null);
    try {
      const page = await listPlans({ limit: PAGE_SIZE, offset });
      setItems((current) => (offset === 0 ? page.items : [...current, ...page.items]));
      setTotal(page.total);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(0);
  }, [load]);

  async function handleDelete(plan) {
    if (!window.confirm(`Delete "${plan.title}"? This can't be undone.`)) return;
    setBusyId(plan.id);
    setMessage(null);
    try {
      await deletePlan(plan.id);
      setItems((current) => current.filter((item) => item.id !== plan.id));
      setTotal((count) => count - 1);
      setMessage("Plan deleted.");
    } catch (err) {
      setError(err);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="container page plans">
      <PageHeader
        eyebrow="Cloud database"
        title="Saved plans"
        actions={
          <Link to="/generate" className="btn btn--primary">
            <Icon name="plus" size={18} />
            Generate new plan
          </Link>
        }
      >
        <p>
          {total} {total === 1 ? "plan" : "plans"} stored in your account, newest first.
        </p>
      </PageHeader>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error.message}</Alert>}

      {!loading && items.length === 0 && !error && (
        <EmptyState
          icon="list"
          title="No saved plans yet"
          action={
            <Link to="/generate" className="btn btn--primary">
              Generate a plan
            </Link>
          }
        >
          Every plan you generate is saved here automatically.
        </EmptyState>
      )}

      {items.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Created</th>
                <th scope="col">Plan</th>
                <th scope="col" className="table__num">
                  Calories
                </th>
                <th scope="col">Engine</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((plan) => (
                <tr key={plan.id}>
                  <td data-label="Created">{formatDateTime(plan.created_at)}</td>
                  <td data-label="Plan">
                    <Link to={`/plans/${plan.id}`} className="link">
                      {plan.title}
                    </Link>
                  </td>
                  <td data-label="Calories" className="table__num">
                    {formatKcal(plan.total_calories, { unit: false })} / {formatKcal(plan.calorie_target)}
                  </td>
                  <td data-label="Engine">
                    <SourceBadge plan={plan} compact />
                  </td>
                  <td className="table__actions">
                    <Link to={`/plans/${plan.id}`} className="btn btn--ghost btn--small">
                      Open
                    </Link>
                    <button
                      type="button"
                      className="btn btn--ghost btn--small btn--danger"
                      onClick={() => handleDelete(plan)}
                      disabled={busyId === plan.id}
                    >
                      {busyId === plan.id ? "Deleting…" : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading && <Loader label="Loading plans" />}
      {!loading && items.length < total && (
        <div className="load-more">
          <button type="button" className="btn btn--secondary" onClick={() => load(items.length)}>
            Show more plans
          </button>
        </div>
      )}
    </div>
  );
}
