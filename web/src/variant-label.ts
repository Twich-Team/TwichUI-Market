// Labels expose upstream identifiers, never infer bonus names or item attributes.
export function variantLabel(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value))
    return "Variant details unavailable";
  const item = value as Record<string, unknown>,
    parts: string[] = [];
  if (Number.isInteger(item.context)) parts.push(`Context ${item.context}`);
  if (Number.isInteger(item.rand)) parts.push(`Random suffix ID ${item.rand}`);
  if (
    Array.isArray(item.bonus_lists) &&
    item.bonus_lists.length &&
    item.bonus_lists.every(Number.isInteger)
  )
    parts.push(
      `Bonus IDs ${item.bonus_lists.slice(0, 6).join(", ")}${item.bonus_lists.length > 6 ? "…" : ""}`,
    );
  if (Array.isArray(item.modifiers) && item.modifiers.length)
    parts.push(`${item.modifiers.length} modifier identifiers`);
  return (
    parts.join(" · ") ||
    (Object.keys(item).every((key) => key === "id")
      ? "Base item identifiers"
      : "Additional item properties")
  );
}
