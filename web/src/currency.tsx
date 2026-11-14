import { money } from "./api";

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
        {parts.map(([amount, metal]) => (
          <span className="currency-part" key={metal}>
            {amount.toLocaleString()}
            <Coin metal={metal} />
          </span>
        ))}
      </span>
    </span>
  );
}
