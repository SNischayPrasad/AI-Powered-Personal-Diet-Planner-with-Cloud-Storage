import { formatNumber } from "../utils/format.js";
import { MEAL_LABELS, optionLabel } from "../utils/options.js";
import Icon from "./Icon.jsx";

export default function MealCard({ slot, meal }) {
  const servings = meal.servings && meal.servings !== 1 ? `${meal.servings} × ` : "";
  return (
    <article className="meal card" id={`meal-${slot}`}>
      <header className="meal__header">
        <p className="eyebrow">{MEAL_LABELS[slot]}</p>
        <h3 className="meal__name">{meal.name}</h3>
        <p className="meal__portion">
          {servings}
          {meal.portion}
        </p>
      </header>

      <p className="meal__description">{meal.description}</p>

      <dl className="meal__nutrition">
        <div>
          <dt>kcal</dt>
          <dd>{formatNumber(meal.calories)}</dd>
        </div>
        <div>
          <dt>Protein</dt>
          <dd>{meal.protein_g} g</dd>
        </div>
        <div>
          <dt>Carbs</dt>
          <dd>{meal.carbs_g} g</dd>
        </div>
        <div>
          <dt>Fat</dt>
          <dd>{meal.fat_g} g</dd>
        </div>
        <div>
          <dt>Fibre</dt>
          <dd>{meal.fiber_g} g</dd>
        </div>
      </dl>

      <p className="meal__ingredients">
        <span className="meal__label">Ingredients</span> {meal.ingredients.join(", ")}
      </p>
      {meal.allergens?.length > 0 && (
        <p className="meal__allergens">
          <span className="meal__label">Contains</span> {meal.allergens.map(optionLabel).join(", ")}
        </p>
      )}
      {meal.why && (
        <p className="meal__why">
          <Icon name="sparkle" size={16} />
          <span>{meal.why}</span>
        </p>
      )}
    </article>
  );
}
