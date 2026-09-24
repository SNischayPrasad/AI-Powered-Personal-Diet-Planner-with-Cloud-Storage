// Profile and plan options. Values mirror ai_engine/options.py on the backend, which is the
// source of truth: the API rejects anything not listed there.

export const SEXES = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "unspecified", label: "Prefer not to say" },
];

export const ACTIVITY_LEVELS = [
  { value: "sedentary", label: "Sedentary", hint: "Little or no exercise" },
  { value: "lightly_active", label: "Lightly active", hint: "Light exercise 1–3 days a week" },
  { value: "moderately_active", label: "Moderately active", hint: "Exercise 3–5 days a week" },
  { value: "very_active", label: "Very active", hint: "Hard exercise 6–7 days a week" },
  { value: "extra_active", label: "Extra active", hint: "Physical job plus training" },
];

export const DIETARY_PREFERENCES = [
  { value: "vegetarian", label: "Vegetarian", hint: "No meat, fish or eggs" },
  { value: "vegan", label: "Vegan", hint: "No animal products at all" },
  { value: "non_vegetarian", label: "General / Non-vegetarian", hint: "Includes meat, fish and eggs" },
];

export const GOALS = [
  { value: "balanced", label: "General balanced eating", hint: "Matches your estimated daily needs" },
  { value: "weight_management", label: "Weight-management demo", hint: "About 15% below, with more protein" },
  { value: "fitness", label: "Fitness-oriented demo", hint: "About 10% above, with more protein" },
];

export const ALLERGENS = [
  { value: "dairy", label: "Dairy" },
  { value: "egg", label: "Egg" },
  { value: "gluten", label: "Gluten" },
  { value: "peanuts", label: "Peanuts" },
  { value: "tree_nuts", label: "Tree nuts" },
  { value: "soy", label: "Soy" },
  { value: "fish", label: "Fish" },
  { value: "shellfish", label: "Shellfish" },
  { value: "sesame", label: "Sesame" },
];

export const CUISINES = [
  { value: "any", label: "Any cuisine" },
  { value: "indian", label: "Indian" },
  { value: "international", label: "International" },
];

export const MEAL_SLOTS = ["breakfast", "lunch", "snack", "dinner"];

export const MEAL_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  snack: "Snack",
  dinner: "Dinner",
};

const LABELS = Object.fromEntries(
  [...SEXES, ...ACTIVITY_LEVELS, ...DIETARY_PREFERENCES, ...GOALS, ...ALLERGENS, ...CUISINES].map(
    (option) => [option.value, option.label],
  ),
);

// Why a plan came from the rule-based engine instead of the AI provider (codes are set by
// ai_engine/planner.py on the backend).
const FALLBACK_REASONS = {
  ai_disabled: "AI was switched off for this plan",
  ai_not_configured: "no AI provider is configured on the server",
  authentication_failed: "the AI provider rejected the API key",
  permission_denied: "the AI API key is not allowed to use this model",
  rate_limited: "the AI provider is busy (rate limited)",
  timeout: "the AI provider took too long to answer",
  network_error: "the AI provider could not be reached",
  refused: "the AI provider declined the request",
  truncated: "the AI answer was cut off",
  empty_response: "the AI provider returned an empty answer",
  invalid_json: "the AI answer was not valid JSON",
  invalid_schema: "the AI answer was missing required fields",
  diet_violation: "the AI suggested food that breaks your diet",
  allergen_violation: "the AI suggested food containing your allergens",
  calorie_mismatch: "the AI meals missed the calorie target",
  inconsistent_nutrition: "the AI's nutrition numbers did not add up",
  invalid_response: "the AI provider sent an unexpected response",
  sdk_missing: "the AI client library is not installed",
};

export function fallbackReasonText(code) {
  if (!code) return "";
  if (code.startsWith("api_error_")) {
    return `the AI provider returned an error (HTTP ${code.slice("api_error_".length)})`;
  }
  return FALLBACK_REASONS[code] ?? code.replaceAll("_", " ");
}

export const FILE_CATEGORY_LABELS = {
  meal_image: "Meal photo",
  document: "Document",
  plan_export: "Saved plan",
};

export function optionLabel(value) {
  if (!value) return "";
  if (LABELS[value]) return LABELS[value];
  const text = String(value).replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
