"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { type Sport } from "@/lib/sports";

interface GameOdds {
  game_id: string;
  home_team: string;
  away_team: string;
  start_time: string;
  odds: Array<{
    sportsbook: string;
    bet_type: string;
    side: string | null;
    line: number;
    odds: number;
  }>;
}

interface OddsResponse {
  sport: string;
  games: GameOdds[];
  count: number;
}

interface OddsDisplayProps {
  sport: Sport;
}

export default function OddsDisplay({ sport }: OddsDisplayProps) {
  const [oddsData, setOddsData] = useState<GameOdds[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchOdds = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get<OddsResponse>(`/odds/${sport}`);
        if (response.success && response.data) {
          setOddsData(response.data.games);
          setError("");
        } else {
          setError(response.error || "Failed to load odds");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchOdds();

    // Poll for odds updates every 15 seconds
    const interval = setInterval(fetchOdds, 15000);

    return () => clearInterval(interval);
  }, [sport]);

  if (loading && oddsData.length === 0) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6 animate-pulse">
            <div className="h-6 bg-gray-300 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
            <div className="space-y-2">
              <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded"></div>
              <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded w-2/3"></div>
            </div>
          </div>
        ))}
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

  if (oddsData.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
        <p className="text-gray-600 dark:text-gray-400">No games available for {sport}</p>
      </div>
    );
  }

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      });
    } catch {
      return dateString;
    }
  };

  // Group odds by sportsbook
  const groupByBook = (odds: GameOdds["odds"]) => {
    const grouped: Record<string, typeof odds> = {};
    odds.forEach((odd) => {
      if (!grouped[odd.sportsbook]) {
        grouped[odd.sportsbook] = [];
      }
      grouped[odd.sportsbook].push(odd);
    });
    return grouped;
  };

  return (
    <div className="space-y-4">
      {oddsData.map((game) => {
        const groupedOdds = groupByBook(game.odds);

        return (
          <div key={game.game_id} className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {game.away_team} @ {game.home_team}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                {formatDate(game.start_time)}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {["DraftKings", "FanDuel", "Kalshi"].map((book) => (
                <div key={book} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                  <h4 className="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-3">
                    {book}
                  </h4>

                  {groupedOdds[book] && groupedOdds[book].length > 0 ? (
                    <div className="space-y-2 text-sm">
                      {groupedOdds[book].map((odd, idx) => {
                        // side carries the team for moneyline and spread, and
                        // already includes the number for totals ("Over 8.0").
                        const label =
                          odd.bet_type === "over_under"
                            ? odd.side || "O/U"
                            : odd.bet_type === "spread"
                            ? `${odd.side || "Spread"} ${odd.line > 0 ? "+" : ""}${odd.line}`
                            : odd.side || "ML";

                        return (
                          <div key={idx} className="flex justify-between items-center gap-2">
                            <span
                              className="text-gray-600 dark:text-gray-400 truncate min-w-0"
                              title={label}
                            >
                              {label}
                            </span>
                            <span className="font-semibold text-gray-900 dark:text-gray-100 shrink-0">
                              {odd.odds > 0 ? "+" : ""}{odd.odds}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500 dark:text-gray-500">No odds available</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {loading && (
        <div className="text-center py-4">
          <p className="text-xs text-gray-600 dark:text-gray-400">
            Updating odds... Last refresh every 15 seconds
          </p>
        </div>
      )}
    </div>
  );
}
