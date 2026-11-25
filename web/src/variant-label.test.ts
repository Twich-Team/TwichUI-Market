import { expect, it } from "vitest";
import { variantLabel } from "./variant-label";

it("uses stable bonus identifiers when names and effects are unverified", () => {
  expect(variantLabel({ id: 25, bonus_lists: [12730] })).toBe("Unknown bonus · 12730");
  expect(variantLabel({ id: 25, context: 0, rand: -5, bonus_lists: [2, 1] }))
    .toBe("Unknown bonuses · 1, 2 · Random suffix ID -5 · Context 0");
  expect(variantLabel({ id: 25, modifiers: [{type: 4, value: 100}] }))
    .toBe("Modifier IDs 4=100");
  expect(variantLabel({ id: 25 })).toBe("Base item");
});

it("keeps unavailable or unrecognized properties distinct from the base item", () => {
  expect(variantLabel(null)).toBe("Variant properties unavailable");
  expect(variantLabel({ id: 25, future_property: 42 })).toBe("Unknown variant properties");
});
