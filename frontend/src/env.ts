export function validateEnv(): void {
  const requiredEnvVars = [
    "NEXT_PUBLIC_API_URL",
  ];

  const missingVars = requiredEnvVars.filter(
    (envVar) => !process.env[envVar]
  );

  if (missingVars.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missingVars.join(", ")}`
    );
  }
}

/**
 * Every backend router is mounted under /api, but the variable is named for
 * the API's URL, so setting it to the bare host is the natural reading -- and
 * that silently 404s every request. Accept either form.
 */
function normalizeApiUrl(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const env = {
  apiUrl: normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"),
} as const;
