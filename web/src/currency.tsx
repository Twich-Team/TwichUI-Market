import { money } from "./api";
import type { ExactCopper } from "./waylaid-crates-data";

// Original inline SVG artwork, authored for TwichUI Market. No external assets.
export function Coin({ metal }: { metal: "gold" | "silver" | "copper" }) {
  return (
    <svg
      className={`coin coin-${metal}`}
      width="13"
      height="13"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="8" cy="8" r="7" fill="currentColor" />
      <circle
        cx="8"
        cy="8"
        r="5"
        fill="none"
        stroke="currentColor"
        className="coin-rim"
      />
      <path
        d="M6 4.5h4M6 11.5h4M8 4.5v7"
        fill="none"
        stroke="currentColor"
        className="coin-rim"
      />
    </svg>
  );
}
export function Currency({ value }: { value: string | null | undefined }) {
  if (value == null || !/^(0|[1-9]\d*)$/.test(value))
    return <span>{money(value)}</span>;
  const total = BigInt(value);
  const parts = [
    [total / 10000n, "gold"],
    [(total % 10000n) / 100n, "silver"],
    [total % 100n, "copper"],
  ] as const;
  return (
    <span
      className="currency"
      role="img"
      aria-label={`${parts[0][0].toLocaleString()} gold, ${parts[1][0]} silver, ${parts[2][0]} copper`}
    >
      <span className="sr-only">{money(value)}</span>
      <span aria-hidden="true">
        {parts
          .filter(
            ([amount, metal]) =>
              amount > 0n || (total === 0n && metal === "copper"),
          )
          .map(([amount, metal]) => (
            <span className="currency-part" key={metal}>
              {amount.toLocaleString()}
              <Coin metal={metal} />
            </span>
          ))}
      </span>
    </span>
  );
}

export function StackUnitPrice({ total, quantity }: { total: string; quantity: number }) {
  const denominator = BigInt(quantity);
  const copper = BigInt(total);
  const remainder = copper % denominator;
  return <><Currency value={String(copper / denominator)}/>
    {remainder > 0n && <span> + {String(remainder)}/{quantity} copper</span>}
  </>;
}

export function ExactCurrency({ copper, exact }: { copper?: string | null; exact?: ExactCopper | null }) {
  if (!exact) return copper == null ? <span className="muted">Unknown</span> : <Currency value={copper}/>;
  const numerator = BigInt(exact.numerator_copper);
  const denominator = BigInt(exact.denominator);
  const rounded = (numerator + denominator / 2n) / denominator;
  if (numerator > 0n && rounded === 0n) {
    return <span className="currency" role="img" aria-label="Less than 1 copper">
      <span className="currency-part" aria-hidden="true">&lt;1<Coin metal="copper"/></span>
    </span>;
  }
  const approximate = numerator % denominator !== 0n;
  return <span title={approximate ? "Rounded to the nearest copper. Sorting uses the exact value." : undefined}>
    {approximate && <><span aria-hidden="true">≈ </span><span className="sr-only">Approximately </span></>}
    <Currency value={String(rounded)}/>
  </span>;
}
