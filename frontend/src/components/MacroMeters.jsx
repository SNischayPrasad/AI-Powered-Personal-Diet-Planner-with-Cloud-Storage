import { formatGrams, formatPercent } from "../utils/format.js";

const MACROS = [
  { key: "protein_g", label: "Protein" },
  { key: "carbs_g", label: "Carbohydrates" },
  { key: "fat_g", label: "Fat" },
];

// Bullet meters: the bar shows what the plan provides; the tick marks the target.
// The scale runs to 150% of the target so being over or under is equally visible.
export default function MacroMeters({ totals, targets }) {
  return (
    <dl className="macros">
      {MACROS.map(({ key, label }) => {
        const actual = totals?.[key] ?? 0;
        const target = targets?.[key] ?? 0;
        const scaleMax = Math.max(target * 1.5, actual, 1);
        return (
          <div className="macros__row" key={key}>
            <dt className="macros__label">{label}</dt>
            <dd className="macros__data">
              <span className="macros__value">
                {formatGrams(actual)}
                <span className="macros__target"> / {formatGrams(target)} target</span>
              </span>
              <span
                className="macros__bar"
                role="img"
                aria-label={`${label}: ${actual} g of a ${target} g target (${formatPercent(
                  target ? actual / target : 0,
                )})`}
              >
                <span className="macros__fill" style={{ width: `${(actual / scaleMax) * 100}%` }} />
                <span className="macros__tick" style={{ left: `${(target / scaleMax) * 100}%` }} />
              </span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
