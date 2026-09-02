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

export const env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
} as const;
