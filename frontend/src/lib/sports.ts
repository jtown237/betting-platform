/**
 * The sports the dashboard can show, in tab order. The backend Sport enum is
 * the source of truth; these strings must match its values exactly, since
 * they are sent straight to /api/odds/{sport}.
 */
export const SPORTS = ["NFL", "CFB", "MLB"] as const;

export type Sport = (typeof SPORTS)[number];
