import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Currency } from "./currency";
it("renders original accessible coins and exact amounts beyond Number precision", () => {
  const html = renderToStaticMarkup(<Currency value="9007199254740993" />);
  expect(html).toContain(
    'aria-label="900,719,925,474 gold, 9 silver, 93 copper"',
  );
  expect((html.match(/<svg/g) || []).length).toBe(3);
  expect(html).toContain("900,719,925,474g 09s 93c");
  expect(html).toContain('aria-hidden="true"');
});
it("does not invent a value for missing or invalid copper", () => {
  expect(renderToStaticMarkup(<Currency value={null} />)).toContain(
    "Unavailable",
  );
  expect(renderToStaticMarkup(<Currency value="1.5" />)).toContain(
    "Invalid price",
  );
});
it("omits zero denominations visually while keeping a complete exact accessible equivalent", () => {
  const gold = renderToStaticMarkup(<Currency value="20000" />);
  expect((gold.match(/<svg/g) || []).length).toBe(1);
  expect(gold).toContain('aria-label="2 gold, 0 silver, 0 copper"');
  const zero = renderToStaticMarkup(<Currency value="0" />);
  expect((zero.match(/<svg/g) || []).length).toBe(1);
  expect(zero).toContain('aria-label="0 gold, 0 silver, 0 copper"');
});
