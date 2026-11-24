export function variantLabel(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "Variant properties unavailable";
  }
  const item = value as Record<string, unknown>;
  const properties: string[] = [];
  if (Array.isArray(item.bonus_lists) && item.bonus_lists.length && item.bonus_lists.every(Number.isInteger)) {
    const ids = [...item.bonus_lists].sort((a, b) => a - b);
    properties.push(`Unknown ${ids.length === 1 ? "bonus" : "bonuses"} · ${ids.join(", ")}`);
  }
  if (Number.isInteger(item.rand)) properties.push(`Random suffix ID ${item.rand}`);
  if (Number.isInteger(item.context)) properties.push(`Context ${item.context}`);
  if (Array.isArray(item.modifiers) && item.modifiers.length) {
    const keys = item.modifiers.flatMap((modifier) =>
      Number.isInteger(modifier?.type) && Number.isInteger(modifier?.value)
        ? [`${modifier.type}=${modifier.value}`]
        : [],
    );
    properties.push(keys.length ? `Modifier IDs ${keys.join(", ")}` : "Unknown modifiers");
  }
  return properties.join(" · ") || (Object.keys(item).every((key) => key === "id") ? "Base item" : "Unknown variant properties");
}
