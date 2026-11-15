import { expect, it } from "vitest";
import { variantLabel } from "./variant-label";
it("keeps verified variant identifiers separate without guessing their names", () => {
  expect(
    variantLabel({ id: 25, context: 0, rand: -5, bonus_lists: [1, 2] }),
  ).toBe("Context 0 · Random suffix ID -5 · Bonus IDs 1, 2");
  expect(variantLabel({ id: 25 })).toBe("Base item identifiers");
});
it("never labels unavailable or unknown variant properties as a base item", () => {
  expect(variantLabel(null)).toBe("Variant details unavailable");
  expect(variantLabel({ id: 25, future_property: 42 })).toBe(
    "Additional item properties",
  );
});
