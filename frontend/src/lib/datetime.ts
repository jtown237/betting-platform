/**
 * The product shows every time in Central, per the design spec, regardless of
 * where the viewer's machine is set. The API sends UTC with an explicit
 * offset, so Date parses it unambiguously and only the display zone is fixed
 * here. Never format an offset-less string: JavaScript reads those as local
 * time, which double-counts the offset.
 */
const CENTRAL = "America/Chicago";

export function formatCentral(dateString?: string | null): string {
  if (!dateString) return "-";
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return dateString;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: CENTRAL,
    timeZoneName: "short",
  });
}
