import { useId, useState } from "react";
import { formatKcal, formatNumber, formatPercent } from "../utils/format.js";
import { MEAL_LABELS } from "../utils/options.js";
import { layoutBowls, ringProgress } from "../utils/thaliLayout.js";

const RING_RADIUS = 190;
// The 2×2 legend mirrors where each bowl sits on the plate.
const LEGEND_ORDER = ["breakfast", "lunch", "dinner", "snack"];

// The day's plan drawn as a steel thali seen from above.
// * One bowl (katori) per meal; bowl AREA is proportional to that meal's calories.
// * The ring around the plate fills towards the day's calorie target.
// * The legend underneath lists every value as text, so nothing depends on the picture.
export default function Thali({ meals, total, target, caption, animate = true }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [active, setActive] = useState(null);
  const bowls = layoutBowls(meals, { center: 200, orbit: 112, maxRadius: 56, minRadius: 30 });
  const ring = ringProgress(total, target, RING_RADIUS);
  const activeBowl = bowls.find((bowl) => bowl.slot === active);

  const summary =
    `Calories by meal: ${bowls.map((b) => `${MEAL_LABELS[b.slot]} ${b.calories}`).join(", ")}. ` +
    `Total ${total} kcal against a ${target} kcal target.`;

  return (
    <figure className="thali">
      <div className="thali__stage">
        <svg
          className={`thali__svg${animate ? " thali__svg--animate" : ""}`}
          viewBox="0 0 400 400"
          role="img"
          aria-labelledby={`${uid}-title`}
        >
          <title id={`${uid}-title`}>{summary}</title>
          <defs>
            <radialGradient id={`${uid}-plate`} cx="50%" cy="44%" r="62%">
              <stop offset="0%" stopColor="#F8FAFA" />
              <stop offset="72%" stopColor="#E3E8EA" />
              <stop offset="100%" stopColor="#C8D0D3" />
            </radialGradient>
            <radialGradient id={`${uid}-katori`} cx="44%" cy="38%" r="70%">
              <stop offset="0%" stopColor="#F5F7F8" />
              <stop offset="100%" stopColor="#B4BFC3" />
            </radialGradient>
          </defs>

          <circle className="thali__ring-track" cx="200" cy="200" r={RING_RADIUS} />
          <circle
            className="thali__ring"
            cx="200"
            cy="200"
            r={RING_RADIUS}
            strokeDasharray={`${ring.dash} ${ring.circumference}`}
            transform="rotate(-90 200 200)"
          />

          <circle className="thali__plate" cx="200" cy="200" r="178" fill={`url(#${uid}-plate)`} />
          <circle className="thali__lip" cx="200" cy="200" r="152" />

          <text className="thali__total" x="200" y="204">
            {formatNumber(total)}
          </text>
          <text className="thali__unit" x="200" y="228">
            kcal planned
          </text>

          {bowls.map((bowl, index) => (
            <g
              key={bowl.slot}
              transform={`translate(${bowl.x} ${bowl.y})`}
              onMouseEnter={() => setActive(bowl.slot)}
              onMouseLeave={() => setActive(null)}
            >
              <g
                className={`thali__bowl${active === bowl.slot ? " is-active" : ""}`}
                style={{ "--delay": `${index * 90}ms` }}
              >
                <circle className="thali__katori" r={bowl.r} fill={`url(#${uid}-katori)`} />
                <circle className="thali__food" r={bowl.r * 0.8} />
                <text className="thali__label" y="5">
                  {MEAL_LABELS[bowl.slot]}
                </text>
              </g>
            </g>
          ))}
        </svg>

        {activeBowl && (
          <div
            className="thali__tooltip"
            role="tooltip"
            style={{ left: `${activeBowl.x / 4}%`, top: `${(activeBowl.y - activeBowl.r) / 4}%` }}
          >
            <span className="thali__tooltip-slot">{MEAL_LABELS[activeBowl.slot]}</span>
            {meals[activeBowl.slot]?.name && (
              <span className="thali__tooltip-name">{meals[activeBowl.slot].name}</span>
            )}
            <span className="thali__tooltip-value">
              {formatKcal(activeBowl.calories)} · {formatPercent(activeBowl.share)} of the day
            </span>
          </div>
        )}
      </div>

      <figcaption className="thali__legend">
        <ul className="thali__legend-list">
          {LEGEND_ORDER.map((slot) => bowls.find((bowl) => bowl.slot === slot)).map((bowl) => (
            <li key={bowl.slot}>
              <span className="thali__legend-slot">{MEAL_LABELS[bowl.slot]}</span>
              <span className="thali__legend-kcal">{formatKcal(bowl.calories)}</span>
              <span className="thali__legend-share">{formatPercent(bowl.share)}</span>
            </li>
          ))}
        </ul>
        <p className="thali__target">
          {formatKcal(total)} of a {formatKcal(target)} target
          {target > 0 && <span className="thali__target-share"> ({formatPercent(total / target)})</span>}
        </p>
        {caption && <p className="thali__caption">{caption}</p>}
      </figcaption>
    </figure>
  );
}
