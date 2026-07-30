const dateFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const numberFormatter = new Intl.NumberFormat("en-US");

export function formatReleaseDate(value: string | null): string {
  if (!value) return "Release date not listed";
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? "Release date not listed"
    : dateFormatter.format(date);
}

export function formatRating(value: number | null): string {
  return value === null ? "Not rated" : `${value.toFixed(1)} / 10`;
}

export function formatRatingCount(value: number): string {
  return `${numberFormatter.format(value)} rating${value === 1 ? "" : "s"}`;
}

export function formatStudio(value: string | null): string {
  return value?.trim() || "Not listed";
}
