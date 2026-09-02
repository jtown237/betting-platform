"use client";

import { useEffect, useState } from "react";
import { tokenManager } from "@/lib/auth";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    setIsAuthenticated(tokenManager.isAuthenticated());
  }, []);

  return (
    <div className="space-y-8">
      <section className="text-center py-12">
        <h2 className="mb-4">Welcome to Betting Platform</h2>
        <p className="text-xl text-gray-600 dark:text-gray-400 mb-8 max-w-2xl mx-auto">
          A modern betting platform built with Next.js, TypeScript, and Tailwind CSS.
          Get started by setting up your account or logging in.
        </p>
        <div className="flex gap-4 justify-center">
          {!isAuthenticated ? (
            <>
              <a
                href="/login"
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium inline-block"
              >
                Sign In
              </a>
              <a
                href="/register"
                className="px-6 py-2 border-2 border-primary-600 text-primary-600 rounded-lg hover:bg-primary-50 dark:hover:bg-primary-900 font-medium inline-block"
              >
                Create Account
              </a>
            </>
          ) : (
            <a
              href="/dashboard"
              className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium inline-block"
            >
              Dashboard
            </a>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
          <h3 className="mb-2">Feature One</h3>
          <p className="text-gray-600 dark:text-gray-400">
            Description of the first feature of the betting platform.
          </p>
        </div>
        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
          <h3 className="mb-2">Feature Two</h3>
          <p className="text-gray-600 dark:text-gray-400">
            Description of the second feature of the betting platform.
          </p>
        </div>
        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
          <h3 className="mb-2">Feature Three</h3>
          <p className="text-gray-600 dark:text-gray-400">
            Description of the third feature of the betting platform.
          </p>
        </div>
      </section>

      <section className="bg-primary-50 dark:bg-primary-950 p-8 rounded-lg border border-primary-200 dark:border-primary-900">
        <h3 className="mb-4">Environment Configuration</h3>
        <div className="bg-white dark:bg-gray-900 p-4 rounded border border-gray-200 dark:border-gray-800">
          <code className="text-sm text-gray-600 dark:text-gray-400">
            NEXT_PUBLIC_API_URL: {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}
          </code>
        </div>
      </section>
    </div>
  );
}
