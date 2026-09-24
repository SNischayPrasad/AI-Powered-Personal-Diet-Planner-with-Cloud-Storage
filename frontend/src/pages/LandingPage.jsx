import { Link } from "react-router-dom";
import CloudStatusPanel from "../components/CloudStatusPanel.jsx";
import Disclaimer from "../components/Disclaimer.jsx";
import Icon from "../components/Icon.jsx";
import Thali from "../components/Thali.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";

// A sample vegetarian day, shown on the plate before anyone signs up.
const SAMPLE_MEALS = {
  breakfast: { name: "Idli with Sambar", calories: 515 },
  lunch: { name: "Rajma Chawal with Cucumber Salad", calories: 700 },
  snack: { name: "Moong Sprouts Chaat", calories: 200 },
  dinner: { name: "Dal Palak with Brown Rice", calories: 625 },
};

const FEATURES = [
  {
    icon: "list",
    title: "Meals that respect your rules",
    body: "Vegetarian, vegan or general diets. Allergens you list are never included. Choose Indian or international dishes.",
  },
  {
    icon: "sparkle",
    title: "Numbers you can check",
    body: "A daily calorie target from a standard formula, calories and macros for every meal, and a hydration estimate.",
  },
  {
    icon: "cloud",
    title: "Saved in the cloud",
    body: "Plans live in a cloud database, and photos and exports in object storage, so they're there on any device you log in from.",
  },
];

const STEPS = [
  { title: "Create your profile", body: "Age, height, weight, activity, diet, goal and allergies (demo data only)." },
  { title: "Generate a plan", body: "Breakfast, lunch, a snack and dinner sized to your daily target." },
  { title: "Save and export", body: "Keep plans in your account and download them as JSON or text." },
  { title: "Open it anywhere", body: "Log in from another device and everything is still there." },
];

const ARCHITECTURE = [
  { icon: "browser", label: "React app", detail: "Runs in your browser" },
  { icon: "server", label: "REST API", detail: "FastAPI · JWT auth" },
  { icon: "sparkle", label: "AI planner", detail: "LLM with rule-based fallback" },
  { icon: "database", label: "Cloud database", detail: "Profiles and plans" },
  { icon: "bucket", label: "Object storage", detail: "Photos and exports" },
];

export default function LandingPage() {
  useDocumentTitle(null);
  const { status } = useAuth();
  const authenticated = status === "authenticated";

  return (
    <div className="landing">
      <section className="hero">
        <div className="container hero__grid">
          <div className="hero__copy">
            <p className="eyebrow">Educational demo · synthetic data only</p>
            <h1 className="hero__title">Plan a day of meals that fits your goal.</h1>
            <p className="hero__lead">
              Enter your diet, goal and allergies. The planner builds breakfast, lunch, a snack and
              dinner with calories and macros, saves them to your cloud account and keeps them
              ready on any device.
            </p>
            <div className="hero__actions">
              {authenticated ? (
                <Link to="/dashboard" className="btn btn--primary btn--large">
                  Open your dashboard
                  <Icon name="arrowRight" size={18} />
                </Link>
              ) : (
                <>
                  <Link to="/register" className="btn btn--primary btn--large">
                    Create a free account
                    <Icon name="arrowRight" size={18} />
                  </Link>
                  <Link to="/login" className="btn btn--secondary btn--large">
                    Log in
                  </Link>
                </>
              )}
            </div>
          </div>
          <div className="hero__visual">
            <Thali meals={SAMPLE_MEALS} total={2040} target={2060} caption="Sample day · vegetarian · balanced eating" />
          </div>
        </div>
      </section>

      <section className="container section" aria-labelledby="features-heading">
        <h2 id="features-heading" className="section__title">What you get</h2>
        <div className="features">
          {FEATURES.map((feature) => (
            <article key={feature.title} className="feature">
              <span className="feature__icon">
                <Icon name={feature.icon} size={22} />
              </span>
              <h3 className="feature__title">{feature.title}</h3>
              <p className="feature__body">{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="container section" aria-labelledby="steps-heading">
        <h2 id="steps-heading" className="section__title">How it works</h2>
        <ol className="steps">
          {STEPS.map((step) => (
            <li key={step.title} className="step">
              <h3 className="step__title">{step.title}</h3>
              <p className="step__body">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="container section" aria-labelledby="cloud-heading">
        <h2 id="cloud-heading" className="section__title">Under the hood</h2>
        <p className="section__lead">
          Each request travels from the browser to a stateless API, which asks the planner for
          meals and keeps structured data and files in two different cloud services.
        </p>
        <div className="architecture-grid">
          <ol className="architecture" aria-label="Request flow">
            {ARCHITECTURE.map((node) => (
              <li key={node.label} className="architecture__node">
                <Icon name={node.icon} size={20} />
                <span className="architecture__label">{node.label}</span>
                <span className="architecture__detail">{node.detail}</span>
              </li>
            ))}
          </ol>
          <CloudStatusPanel title="This deployment" />
        </div>
      </section>

      <section className="container section section--last">
        <Disclaimer />
      </section>
    </div>
  );
}
