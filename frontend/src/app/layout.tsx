import type { Metadata } from "next";
import "@/globals.css";

export const metadata: Metadata = {
  title: "Betting Platform",
  description: "A modern betting platform built with Next.js",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex flex-col min-h-screen">
          <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
            <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-primary-600">
                  BettingPlatform
                </h1>
              </div>
            </nav>
          </header>
          <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-8">
            {children}
          </main>
          <footer className="bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
              <p className="text-center text-gray-600 dark:text-gray-400">
                © 2026 Betting Platform. All rights reserved.
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
