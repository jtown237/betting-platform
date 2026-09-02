"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

interface UserProfileData {
  email: string;
  initial_bankroll: number;
  total_returns: number;
  total_bets: number;
  bets_won: number;
  bets_lost: number;
  bets_push: number;
  roi_percent: number;
}

export default function UserProfile() {
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get<UserProfileData>("/user/profile");
        if (response.success && response.data) {
          setProfile(response.data);
        } else {
          setError(response.error || "Failed to load profile");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6 animate-pulse">
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded"></div>
          <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-red-200 dark:border-red-800 p-6">
        <p className="text-red-600 dark:text-red-400">{error || "Failed to load profile"}</p>
      </div>
    );
  }

  const currentBankroll = profile.initial_bankroll + profile.total_returns;

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">{profile.email}</h2>
        <p className="text-gray-600 dark:text-gray-400">User Profile</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">Bankroll</p>
          <p className="text-2xl font-bold text-primary-600 mt-1">
            ${currentBankroll.toFixed(2)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            Starting: ${profile.initial_bankroll.toFixed(2)}
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">Returns</p>
          <p className={`text-2xl font-bold mt-1 ${profile.total_returns >= 0 ? "text-green-600" : "text-red-600"}`}>
            {profile.total_returns >= 0 ? "+" : ""}{profile.total_returns.toFixed(2)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">Net P&L</p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">ROI</p>
          <p className={`text-2xl font-bold mt-1 ${profile.roi_percent >= 0 ? "text-green-600" : "text-red-600"}`}>
            {profile.roi_percent.toFixed(2)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">Return on Investment</p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">Record</p>
          <p className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">
            {profile.bets_won}-{profile.bets_lost}-{profile.bets_push}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">W-L-P ({profile.total_bets} total)</p>
        </div>
      </div>
    </div>
  );
}
