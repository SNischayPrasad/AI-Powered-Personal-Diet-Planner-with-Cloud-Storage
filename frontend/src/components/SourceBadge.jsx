import { fallbackReasonText } from "../utils/options.js";
import Icon from "./Icon.jsx";

const PROVIDER_NAMES = {
  anthropic: "Claude",
  openai_compatible: "OpenAI-compatible API",
};

// Shows which engine produced a plan — and, when the AI was skipped, why.
export default function SourceBadge({ plan, compact = false }) {
  if (plan.source === "ai") {
    const provider = PROVIDER_NAMES[plan.ai_provider] ?? plan.ai_provider;
    return (
      <span className="badge badge--ai">
        <Icon name="sparkle" size={14} />
        AI · {provider}
        {!compact && plan.ai_model && <span className="badge__detail">{plan.ai_model}</span>}
      </span>
    );
  }
  return (
    <span className="source">
      <span className="badge badge--rules">
        <Icon name="list" size={14} />
        Rule-based engine
      </span>
      {!compact && plan.fallback_reason && (
        <span className="source__note">Used because {fallbackReasonText(plan.fallback_reason)}.</span>
      )}
    </span>
  );
}
