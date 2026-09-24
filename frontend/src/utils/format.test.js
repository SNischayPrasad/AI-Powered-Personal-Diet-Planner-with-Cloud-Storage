import { describe, expect, it } from "vitest";
import { formatBytes, formatDate, formatDateTime, formatKcal, formatPercent } from "./format.js";
import { fallbackReasonText, optionLabel } from "./options.js";

describe("formatKcal", () => {
  it("adds thousands separators and the unit", () => {
    expect(formatKcal(2072)).toBe("2,072 kcal");
    expect(formatKcal(980)).toBe("980 kcal");
  });

  it("can omit the unit for compact tables", () => {
    expect(formatKcal(2072, { unit: false })).toBe("2,072");
  });
});

describe("formatBytes", () => {
  it.each([
    [0, "0 B"],
    [900, "900 B"],
    [1536, "1.5 KB"],
    [4 * 1024 * 1024, "4.0 MB"],
  ])("formats %i bytes as %s", (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });
});

describe("dates", () => {
  const iso = "2026-09-24T15:42:07.123456+00:00";

  it("formats a date in the requested time zone", () => {
    expect(formatDate(iso, { timeZone: "UTC" })).toBe("24 Sept 2026");
    expect(formatDate(iso, { timeZone: "Asia/Kolkata" })).toBe("24 Sept 2026");
  });

  it("formats date and time in the requested time zone", () => {
    expect(formatDateTime(iso, { timeZone: "UTC" })).toBe("24 Sept 2026, 15:42");
    expect(formatDateTime(iso, { timeZone: "Asia/Kolkata" })).toBe("24 Sept 2026, 21:12");
  });
});

describe("formatPercent", () => {
  it("rounds a ratio to a whole percentage", () => {
    expect(formatPercent(0.3512)).toBe("35%");
    expect(formatPercent(1.089)).toBe("109%");
  });
});

describe("optionLabel", () => {
  it("returns the human label for option values sent by the API", () => {
    expect(optionLabel("weight_management")).toBe("Weight-management demo");
    expect(optionLabel("non_vegetarian")).toBe("General / Non-vegetarian");
    expect(optionLabel("tree_nuts")).toBe("Tree nuts");
  });

  it("falls back to a readable version of unknown values", () => {
    expect(optionLabel("something_new")).toBe("Something new");
  });
});

describe("fallbackReasonText", () => {
  it("explains why the rule-based engine was used instead of the AI", () => {
    expect(fallbackReasonText("timeout")).toBe("the AI provider took too long to answer");
    expect(fallbackReasonText("api_error_529")).toBe("the AI provider returned an error (HTTP 529)");
    expect(fallbackReasonText(null)).toBe("");
  });
});
