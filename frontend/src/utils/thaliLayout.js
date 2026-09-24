// Geometry for the thali visual: a steel plate with one bowl (katori) per meal.
//
// Honest encoding: a bowl's AREA is proportional to its calories, so the radius scales with
// the square root. Meals sit clockwise from the top-left, like a clock face:
// breakfast → lunch → snack → dinner.

export const SLOT_ORDER = ["breakfast", "lunch", "snack", "dinner"];

// Degrees in SVG coordinates (0° = east, angles grow clockwise because y points down).
const SLOT_ANGLES = { breakfast: 225, lunch: 315, snack: 45, dinner: 135 };

export function layoutBowls(meals, { center = 200, orbit = 110, maxRadius = 56, minRadius = 30 } = {}) {
  const calories = SLOT_ORDER.map((slot) => Math.max(0, Number(meals?.[slot]?.calories) || 0));
  const total = calories.reduce((sum, value) => sum + value, 0);
  const largest = Math.max(...calories, 1);

  return SLOT_ORDER.map((slot, index) => {
    const angle = (SLOT_ANGLES[slot] * Math.PI) / 180;
    const radius = maxRadius * Math.sqrt(calories[index] / largest);
    return {
      slot,
      calories: calories[index],
      share: total ? calories[index] / total : 0,
      r: Math.max(minRadius, radius),
      x: center + orbit * Math.cos(angle),
      y: center + orbit * Math.sin(angle),
    };
  });
}

// Progress ring around the plate: the full circle is the day's calorie target.
export function ringProgress(total, target, radius) {
  const circumference = 2 * Math.PI * radius;
  const fraction = target > 0 ? Math.min(Math.max(total / target, 0), 1) : 0;
  return { circumference, fraction, dash: fraction * circumference };
}
