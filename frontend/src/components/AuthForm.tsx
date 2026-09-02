"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { tokenManager } from "@/lib/auth";

interface AuthFormProps {
  type: "login" | "register";
  onSuccess?: () => void;
}

export default function AuthForm({ type, onSuccess }: AuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bankroll, setBankroll] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      errors.email = "Email is required";
    } else if (!emailRegex.test(email)) {
      errors.email = "Please enter a valid email address";
    }

    // Password validation
    if (!password) {
      errors.password = "Password is required";
    } else if (password.length < 8) {
      errors.password = "Password must be at least 8 characters";
    }

    // Bankroll validation (register only)
    if (type === "register") {
      if (!bankroll.trim()) {
        errors.bankroll = "Initial bankroll is required";
      } else {
        const bankrollNum = parseFloat(bankroll);
        if (isNaN(bankrollNum) || bankrollNum <= 0) {
          errors.bankroll = "Bankroll must be a positive number";
        }
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      if (type === "login") {
        const response = await apiClient.post<{
          user_id: number;
          token: string;
        }>("/auth/login", {
          email,
          password,
        });

        if (!response.success || !response.data) {
          setError(response.error || "Login failed");
          return;
        }

        // Store token and user_id
        tokenManager.setToken({
          accessToken: response.data.token,
          userId: response.data.user_id,
        });

        onSuccess?.();
        router.push("/dashboard");
      } else {
        const response = await apiClient.post<{
          user_id: number;
          token: string;
        }>("/auth/register", {
          email,
          password,
          initial_bankroll: parseFloat(bankroll),
        });

        if (!response.success || !response.data) {
          setError(response.error || "Registration failed");
          return;
        }

        // Store token and user_id
        tokenManager.setToken({
          accessToken: response.data.token,
          userId: response.data.user_id,
        });

        onSuccess?.();
        router.push("/dashboard");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      );
    } finally {
      setLoading(false);
    }
  };

  const title = type === "login" ? "Sign In" : "Create Account";
  const submitText = type === "login" ? "Sign In" : "Create Account";
  const toggleLink = type === "login" ? "/register" : "/login";
  const toggleText = type === "login" ? "Don't have an account? Register" : "Already have an account? Sign In";

  return (
    <div className="max-w-md w-full mx-auto">
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-8">
        <h1 className="text-center mb-8">{title}</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (validationErrors.email) {
                  const newErrors = { ...validationErrors };
                  delete newErrors.email;
                  setValidationErrors(newErrors);
                }
              }}
              className={`w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                validationErrors.email
                  ? "border-red-500 dark:border-red-500"
                  : "border-gray-300 dark:border-gray-700"
              }`}
              placeholder="you@example.com"
              disabled={loading}
            />
            {validationErrors.email && (
              <p className="text-red-600 dark:text-red-400 text-xs mt-1">
                {validationErrors.email}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium mb-2"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (validationErrors.password) {
                  const newErrors = { ...validationErrors };
                  delete newErrors.password;
                  setValidationErrors(newErrors);
                }
              }}
              className={`w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                validationErrors.password
                  ? "border-red-500 dark:border-red-500"
                  : "border-gray-300 dark:border-gray-700"
              }`}
              placeholder="••••••••"
              disabled={loading}
            />
            {validationErrors.password && (
              <p className="text-red-600 dark:text-red-400 text-xs mt-1">
                {validationErrors.password}
              </p>
            )}
          </div>

          {type === "register" && (
            <div>
              <label
                htmlFor="bankroll"
                className="block text-sm font-medium mb-2"
              >
                Initial Bankroll
              </label>
              <input
                id="bankroll"
                type="number"
                step="0.01"
                value={bankroll}
                onChange={(e) => {
                  setBankroll(e.target.value);
                  if (validationErrors.bankroll) {
                    const newErrors = { ...validationErrors };
                    delete newErrors.bankroll;
                    setValidationErrors(newErrors);
                  }
                }}
                className={`w-full px-4 py-2 border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  validationErrors.bankroll
                    ? "border-red-500 dark:border-red-500"
                    : "border-gray-300 dark:border-gray-700"
                }`}
                placeholder="1000.00"
                disabled={loading}
              />
              {validationErrors.bankroll && (
                <p className="text-red-600 dark:text-red-400 text-xs mt-1">
                  {validationErrors.bankroll}
                </p>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-primary-400 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {loading ? "Loading..." : submitText}
          </button>
        </form>

        <div className="mt-6 text-center text-sm">
          <a href={toggleLink} className="font-medium">
            {toggleText}
          </a>
        </div>
      </div>
    </div>
  );
}
