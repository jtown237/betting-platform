"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { formatCentral } from "@/lib/datetime";

interface ActiveBet {
  bet_id: number;
  status: string;
  amount?: number;
  picked_side?: string;
  odds_locked_at?: number;
  payout?: number;
  created_at?: string;
  settled_at?: string;
  notes?: string;
  game_id?: string;
  sportsbook?: string;
  bet_type?: string;
}

export default function ActiveBets() {
  const [bets, setBets] = useState<ActiveBet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchActiveBets = async () => {
      try {
        const response = await apiClient.get<ActiveBet[]>("/bets/active");
        if (response.success && response.data) {
          setBets(response.data);
          setError("");
        } else {
          setError(response.error || "Failed to load active bets");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchActiveBets();
  }, []);

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6 animate-pulse">
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-12 bg-gray-300 dark:bg-gray-700 rounded"></div>
          <div className="h-12 bg-gray-300 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-red-200 dark:border-red-800 p-6">
        <p className="text-red-600 dark:text-red-400">{error}</p>
      </div>
    );
  }

  if (bets.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
        <h2 className="text-xl font-bold mb-4">Active Bets</h2>
        <p className="text-gray-600 dark:text-gray-400">No active bets at this time</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
      <h2 className="text-xl font-bold mb-4">Active Bets ({bets.length})</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Bet
              </th>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Amount
              </th>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Odds
              </th>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Side
              </th>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Book
              </th>
              <th className="text-left py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {bets.map((bet) => (
              <tr key={bet.bet_id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                <td className="py-3 px-4 text-gray-900 dark:text-gray-100">
                  <div className="font-medium">
                    {bet.game_id || bet.notes || `Bet #${bet.bet_id}`}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {bet.bet_type}
                  </div>
                </td>
                <td className="py-3 px-4 font-semibold text-gray-900 dark:text-gray-100">
                  ${bet.amount?.toFixed(2) || "0.00"}
                </td>
                <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                  {bet.odds_locked_at ? `${bet.odds_locked_at > 0 ? "+" : ""}${bet.odds_locked_at}` : "-"}
                </td>
                <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                  {bet.picked_side}
                </td>
                <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                  {bet.sportsbook || "-"}
                </td>
                <td className="py-3 px-4 text-gray-600 dark:text-gray-400 text-xs">
                  {formatCentral(bet.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
