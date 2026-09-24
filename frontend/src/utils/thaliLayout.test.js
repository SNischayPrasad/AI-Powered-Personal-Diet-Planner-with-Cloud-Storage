import { describe, expect, it } from "vitest";
import { layoutBowls, ringProgress, SLOT_ORDER } from "./thaliLayout.js";

const meals = {
  breakfast: { calories: 510 },
  lunch: { calories: 720 },
  snack: { calories: 180 },
  dinner: { calories: 620 },
};

describe("layoutBowls", () => {
  const bowls = layoutBowls(meals, { center: 200, orbit: 110, maxRadius: 56, minRadius: 20 });
  const bySlot = Object.fromEntries(bowls.map((bowl) => [bowl.slot, bowl]));

  it("returns one bowl per meal in day order", () => {
    expect(bowls.map((bowl) => bowl.slot)).toEqual(SLOT_ORDER);
  });

  it("gives the biggest meal the maximum radius", () => {
    expect(bySlot.lunch.r).toBeCloseTo(56);
  });

  it("makes bowl AREA proportional to calories (not radius)", () => {
    const areaRatio = bySlot.snack.r ** 2 / bySlot.lunch.r ** 2;
    expect(areaRatio).toBeCloseTo(180 / 720, 5);
  });

  it("never draws a bowl smaller than the minimum readable radius", () => {
    const tiny = layoutBowls({ ...meals, snack: { calories: 5 } }, { minRadius: 30 });
    expect(tiny.find((bowl) => bowl.slot === "snack").r).toBe(30);
  });

  it("reports each meal's share of the day", () => {
    expect(bySlot.lunch.share).toBeCloseTo(720 / 2030, 5);
    expect(bowls.reduce((sum, bowl) => sum + bowl.share, 0)).toBeCloseTo(1, 5);
  });

  it("places meals clockwise from the top-left like a clock face", () => {
    expect(bySlot.breakfast.x).toBeLessThan(200);
    expect(bySlot.breakfast.y).toBeLessThan(200);
    expect(bySlot.lunch.x).toBeGreaterThan(200);
    expect(bySlot.lunch.y).toBeLessThan(200);
    expect(bySlot.snack.x).toBeGreaterThan(200);
    expect(bySlot.snack.y).toBeGreaterThan(200);
    expect(bySlot.dinner.x).toBeLessThan(200);
    expect(bySlot.dinner.y).toBeGreaterThan(200);
  });
});

describe("ringProgress", () => {
  it("fills the ring in proportion to total versus target", () => {
    const ring = ringProgress(1030, 2060, 100);
    expect(ring.fraction).toBeCloseTo(0.5);
    expect(ring.dash).toBeCloseTo(Math.PI * 100);
  });

  it("caps the ring at a full circle when the target is exceeded", () => {
    expect(ringProgress(2500, 2000, 100).fraction).toBe(1);
  });

  it("shows an empty ring when there is no target", () => {
    expect(ringProgress(500, 0, 100).fraction).toBe(0);
  });
});
