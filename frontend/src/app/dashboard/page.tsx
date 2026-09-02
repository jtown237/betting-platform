"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { tokenManager } from "@/lib/auth";
import Navigation from "@/components/Navigation";
import UserProfile from "@/components/UserProfile";
import OddsDisplay from "@/components/OddsDisplay";
import ActiveBets from "@/components/ActiveBets";

type Sport = "NFL" | "CFB";

export default function Dashboard() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [sport, setSport] = useState<Sport>("NFL");

  useEffect(() => {
    // Check authentication
    const authenticated = tokenManager.isAuthenticated();
    if (!authenticated) {
      router.push("/login");
      return;
    }
    setIsAuthenticated(true);
    setIsLoading(false);
  }, [router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <Navigation />
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-8">
        <div className="space-y-8">
          {/* User Profile Section */}
          <section>
            <UserProfile />
          </section>

          {/* Odds and Bets Section */}
          <section>
            <div className="mb-6">
              <div className="flex items-center gap-4 border-b border-gray-200 dark:border-gray-800">
                {(["NFL", "CFB"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSport(s)}
                    className={`px-4 py-3 font-medium text-sm transition-colors border-b-2 ${
                      sport === s
                        ? "text-primary-600 border-primary-600 dark:text-primary-400 dark:border-primary-400"
                        : "text-gray-600 dark:text-gray-400 border-transparent hover:text-gray-900 dark:hover:text-gray-200"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-8">
              {/* Odds Display */}
              <div>
                <h2 className="text-2xl font-bold mb-4">{sport} Games & Odds</h2>
                <OddsDisplay sport={sport} />
              </div>

              {/* Active Bets */}
              <div>
                <ActiveBets />
              </div>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
