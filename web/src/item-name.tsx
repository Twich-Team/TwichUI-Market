/** Name colors come only from normalized metadata, never from a name or icon. */
export const ITEM_QUALITY_COLORS = {
  POOR: "#9D9D9D", COMMON: "#FFFFFF", UNCOMMON: "#1EFF00", RARE: "#0070DD",
  EPIC: "#A335EE", LEGENDARY: "#FF8000", ARTIFACT: "#E6CC80",
} as const;
const HIGH_CONTRAST_ITEM_QUALITY_COLORS: Partial<Record<keyof typeof ITEM_QUALITY_COLORS, string>> = {
  RARE: "#57A2FF", EPIC: "#CF89FF",
};
export const UNKNOWN_ITEM_COLOR = "#D6D0C4";
export function itemQuality(value?: string | null): keyof typeof ITEM_QUALITY_COLORS | null {
  const key = value?.trim().toUpperCase();
  return key && Object.prototype.hasOwnProperty.call(ITEM_QUALITY_COLORS,key) ? key as keyof typeof ITEM_QUALITY_COLORS : null;
}
export function itemQualityColor(value?: string | null) { const key=itemQuality(value); return key ? ITEM_QUALITY_COLORS[key] : UNKNOWN_ITEM_COLOR; }
export function ItemName({ name, quality, highContrast = false }: { name: string; quality?: string | null; highContrast?: boolean }) {
  const normalized=itemQuality(quality);
  const enhanced = highContrast && normalized ? HIGH_CONTRAST_ITEM_QUALITY_COLORS[normalized] : undefined;
  return <span className="item-name" data-quality={normalized?.toLowerCase() || "unknown"} title={normalized ? `${normalized.charAt(0)}${normalized.slice(1).toLowerCase()} quality` : "Quality unknown"} style={{color:enhanced ?? itemQualityColor(quality)}}>{name}</span>;
}
