# Phase 1 Design: Betting Platform for NFL/CFB

**Date:** 2026-08-31  
**Scope:** MVP betting tracker with automatic odds aggregation and result reconciliation  
**Sports:** NFL, College Football  
**Budget:** ~$20/month hosting

---

## 1. Architecture Overview

The platform consists of five interconnected subsystems:

### 1.1 Frontend (Next.js + React)
- User interface for placing bets, viewing active bets, and tracking P&L
- Displays live odds from all sportsbooks (DraftKings, FanDuel, Kalshi)
- Polls backend for real-time odds updates every 10-15 seconds
- Responsive design for mobile/desktop

### 1.2 Backend API (FastAPI + Python)
- REST API serving odds, managing bets, handling user authentication
- Exposes endpoints for bet placement, history, and stats
- Orchestrates background jobs
- Runs on Railway or equivalent ($5-10/month)

### 1.3 Data Pipelines (Background Jobs)
- **Odds polling:** Calls OddsAPI every 10 minutes, stores latest odds per game/book/bet-type
- **Score reconciliation:** Pulls game results hourly (6pm-5am) from ESPN/NFL APIs
- **Auto-settlement:** Matches completed games against open bets, marks won/lost/push
- **Scheduled via APScheduler (Python)**

### 1.4 Database (PostgreSQL)
- Managed via Railway or Render (~$5-10/month)
- Stores users, bets, games, odds (latest only in Phase 1), team stats
- Designed for easy addition of sports/bet types in Phase 2

### 1.5 External APIs
- **OddsAPI** — aggregates odds from DraftKings, FanDuel, Kalshi (free tier sufficient at 10-min polling)
- **ESPN/NFL APIs** — game scores and final results
- Advanced stats sources (Pro Football Reference, ESPN) — deferred to Phase 2

---

## 2. Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Frontend | Next.js 14 + React + TypeScript | Deployed on Vercel (free tier) |
| Backend | FastAPI + Python 3.11 | Deployed on Railway (~$5-10/month) |
| Database | PostgreSQL 15 | Managed Postgres on Railway (~$5-10/month) |
| Background Jobs | APScheduler (Python) | Runs in backend container |
| Real-time Updates | HTTP polling (simple) | WebSockets deferred to Phase 2 if needed |
| Authentication | JWT tokens + bcrypt | Session-based, stateless |
| Deployment | Vercel (frontend) + Railway (backend+DB) | Total budget ~$20/month |

---

## 3. Data Model

### 3.1 Users Table
```
users
├── id (PK)
├── email (unique)
├── password_hash
├── created_at
├── updated_at
├── initial_bankroll (decimal, required Phase 1 — user's starting amount)
└── total_returns (decimal, calculated as sum of all payouts - initial_bankroll)
```

### 3.2 Bets Table
```
bets
├── id (PK)
├── user_id (FK → users)
├── game_id (FK → games, ESPN ID, nullable for custom bets)
├── sportsbook (enum: DraftKings, FanDuel, Kalshi, Custom)
├── bet_type (enum: spread, moneyline, over_under, prop, custom)
├── amount (dollars)
├── picked_side (string: e.g., "Chiefs +3" or "Over 47.5" or "Mahomes 250+ passing yards")
├── odds_at_placement (decimal, locked at game start time, nullable for custom)
├── status (enum: pending, won, lost, push)
├── payout (decimal, calculated after settlement)
├── created_at (bet placement)
├── game_start_time (locked from game, used for line locking, nullable for custom)
├── settled_at (when result was determined)
└── notes (string, optional — for custom bets, user can store notes)
```
**Note:** Multiple bets per game per user are allowed. Custom bets (non-OddsAPI) have nullable game_id and game_start_time; users manually mark them as won/lost.
```

### 3.3 Games Table
```
games
├── id (PK, ESPN game ID: e.g., "401547382")
├── sport (enum: NFL, CFB)
├── home_team (string)
├── away_team (string)
├── start_time (datetime)
├── final_score_home (int, nullable until game completes)
├── final_score_away (int, nullable until game completes)
├── status (enum: scheduled, live, completed)
├── created_at
└── updated_at
```

### 3.4 Odds Table
```
odds
├── id (PK)
├── game_id (FK → games)
├── sportsbook (enum: DraftKings, FanDuel, Kalshi)
├── bet_type (enum: spread, moneyline, over_under)
├── line (decimal: e.g., 3.0 for spread, 1.5 for total)
├── odds (decimal: e.g., -110)
├── timestamp (when fetched from OddsAPI)
└── game_start_time (denormalized from games, for reference)
```
**Note:** Odds table stores *only* the latest record per (game_id, sportsbook, bet_type) in Phase 1. Odds history will be added in Phase 2 for backtesting.

### 3.5 Team Stats Table (Phase 1 — minimal)
```
team_stats
├── id (PK)
├── team_id (string: e.g., "KC" for Kansas City Chiefs)
├── sport (enum: NFL, CFB)
├── season (int: e.g., 2025)
├── stat_key (enum: off_efficiency, def_efficiency, etc.)
├── stat_value (decimal)
├── last_updated (datetime)
└── source (string: e.g., "Pro Football Reference")
```
**Note:** Advanced stats deferred to Phase 2. Phase 1 can have a simple stub for UI placeholders.

---

## 4. API Endpoints (MVP)

### 4.1 Odds Endpoints
```
GET /api/odds/{sport}
├── Returns all active games for a sport with latest odds from all books
├── Response: [{ game_id, home_team, away_team, start_time, odds: [...] }]

GET /api/odds/{game_id}
├── Returns detailed odds for a specific game
├── Response: { game_id, odds: [{ sportsbook, bet_type, line, odds }] }
```

### 4.2 Bet Endpoints
```
POST /api/bets
├── User places a bet (OddsAPI-sourced)
├── Body: { game_id, sportsbook, bet_type, amount, picked_side }
├── Returns: { bet_id, status: "pending", odds_locked_at: game_start_time }

POST /api/bets/custom
├── User creates a custom bet (prop, alternate line, freeform)
├── Body: { amount, picked_side, odds: optional, notes: optional }
├── Returns: { bet_id, status: "pending" }
├── Note: No game_id or automatic settlement; user manually marks as won/lost

GET /api/bets/active
├── Returns all open bets for the authenticated user
├── Response: [{ bet_id, game, amount, status, current_score, bet_type }]

GET /api/bets/history
├── Returns settled bets with results and P&L
├── Response: [{ bet_id, game, result, payout, status: "won|lost|push" }]

GET /api/bets/{bet_id}
├── Returns details of a specific bet
├── Response: { bet_id, game, amount, status, odds_locked, result_if_complete }

PATCH /api/bets/{bet_id}/settle
├── User manually settles a custom bet
├── Body: { result: "won|lost|push", payout: optional }
├── Returns: { bet_id, status, payout, settled_at }
```

### 4.3 Authentication Endpoints
```
POST /api/auth/register
├── Body: { email, password }
├── Returns: { user_id, token }

POST /api/auth/login
├── Body: { email, password }
├── Returns: { user_id, token }

POST /api/auth/logout
├── Invalidates session (optional if using JWT)
```

### 4.4 User Endpoints
```
GET /api/user/profile
├── Returns authenticated user's profile, bankroll, and returns
├── Response: { email, initial_bankroll, total_returns, total_bets, bets_won, bets_lost, bets_push, roi_percent }
```

---

## 5. Odds Polling & Storage Strategy

### 5.1 Polling Mechanism
- **Frequency:** Every 10 minutes
- **Source:** OddsAPI (aggregates DraftKings, FanDuel, Kalshi)
- **Implementation:** APScheduler background job in FastAPI
- **Cost:** OddsAPI free tier covers ~144 calls/day; ample headroom

### 5.2 Storage Logic
```
FOR each game in NFL/CFB:
  CALL OddsAPI.get_odds(game_id)
  FOR each sportsbook in response:
    FOR each bet_type in (spread, moneyline, over_under):
      UPSERT into odds table (game_id, sportsbook, bet_type)
      └─ Keep only latest record per tuple (no history yet)
```

### 5.3 Frontend Polling
- Frontend polls `GET /api/odds/{sport}` every 10-15 seconds
- Displays live odds in real-time
- No WebSockets in Phase 1 (HTTP polling sufficient)

---

## 6. Bet Placement & Line Locking

### 6.1 Placement Flow
1. User views a game and its odds (e.g., Chiefs -3 at DraftKings)
2. User enters amount and clicks "Place Bet"
3. Backend creates a `bets` record in `pending` status with:
   - `odds_at_placement` = current odds from sportsbook
   - `game_start_time` = locked from games table
4. Frontend shows "Bet placed" confirmation

### 6.2 Line Locking at Game Time
- **Locking happens at `game_start_time`**, not at bet placement
- When the game starts, we update the `odds_at_placement` to the locked value
- This prevents odds movement between placement and kickoff from affecting the bet outcome
- Implementation: Scheduled job 2 minutes before each game start, locks lines for all pending bets on that game

### 6.3 Validation
- Allow multiple bets per game per user (no duplicate prevention)
- Validate amount > 0
- Validate game hasn't started yet (if linked to OddsAPI game)
- For custom bets, no game validation required

---

## 7. Game Results Reconciliation

### 7.1 Score Pulling Schedule
- **Frequency:** Every hour from 6pm to 5am Central Time
- **Source:** ESPN/NFL APIs
- **Triggered by:** APScheduler cron job
- **Covers:** Evening games (usually 6pm-8pm CT) through late-night games
- **Retry Logic:** If API fetch fails, log error and retry on next scheduled hour (no immediate retry, to avoid rate limits)

### 7.2 Reconciliation Logic
```
FOR each completed game:
  FETCH final_score_home, final_score_away from ESPN
  UPDATE games table with final scores, status = "completed"
  
  FOR each open bet on this game:
    CALL settle_bet(bet, final_score)
    └─ Determine if won, lost, or push based on bet_type and picked_side
    └─ Calculate payout
    └─ Update bet.status and bet.settled_at
```

### 7.3 Settlement Logic by Bet Type

**Spread Bet:**
- Spread: Chiefs -3
- Final: Chiefs 24, Bills 21 (difference +3)
- Result: **Push** (line = difference, so no winner)
- Payout: Return stake

- Spread: Chiefs -3
- Final: Chiefs 27, Bills 21 (difference +6)
- Result: **Win** (Chiefs covered more than -3)
- Payout: stake × (1 + abs(odds/100))

- Spread: Chiefs -3
- Final: Chiefs 20, Bills 21 (difference -1)
- Result: **Loss** (Chiefs didn't cover)
- Payout: 0

**Moneyline Bet:**
- Pick: Chiefs (moneyline)
- Final: Chiefs wins
- Result: **Win**
- Payout: stake × (1 + odds/100) if odds are negative (e.g., -110 → 1.91x)

**Over/Under Bet:**
- Pick: Over 47.5
- Final: 48 total points
- Result: **Win**
- Payout: stake × (1 + abs(odds/100))

### 7.4 Edge Cases
- **Push:** Both sides return the original stake (not counted as loss or win in user P&L)
- **Cancelled game:** Mark bet as `cancelled`, return stake
- **Line moved:** Use `odds_at_placement` (locked at game start), ignore current line
- **Delayed/rescheduled game:** Check ESPN for updated start time, adjust reconciliation accordingly

---

## 8. User Authentication

### 8.1 Registration
- Email + password (no social login in Phase 1)
- Password hashed with bcrypt
- Validation: email format, password strength (min 8 chars)
- Returns JWT token for immediate login

### 8.2 Login
- Email + password → JWT token
- Token includes user_id, expires in 30 days
- Frontend stores token in httpOnly cookie (secure)

### 8.3 Protected Routes
- All `/api/bets/*` and `/api/user/*` require valid JWT
- Backend validates token, extracts user_id for authorization

---

## 9. Phase 1 Scope & Constraints

### What's Included
- ✅ NFL and CFB odds from DraftKings, FanDuel, Kalshi
- ✅ Full-game odds only (spread, moneyline, over/under)
- ✅ Bet placement and tracking
- ✅ Automatic result settlement (6pm-5am hourly)
- ✅ User authentication
- ✅ P&L summary per user
- ✅ ~$20/month budget

### What's Deferred to Phase 2
- ❌ Odds history and backtesting database
- ❌ Advanced stats (DVOA, FEI, efficiency ratings)
- ❌ Player props, quarter bets, live bets
- ❌ Leaderboard / head-to-head competitions
- ❌ WebSockets for real-time odds (HTTP polling sufficient)
- ❌ Additional sports (NBA, MLB, etc.)
- ❌ Weather integration
- ❌ Predictive modeling / contrarian bias detection

### What's Out of Scope Indefinitely
- Real money settlement / payment processing
- Gambling compliance / regulatory features
- APIs for external integrations
- Mobile app (responsive web only)

---

## 10. Deployment & Infrastructure

### 10.1 Frontend
- Repository: `/frontend` (Next.js)
- Deployment: Vercel (free tier)
- Environment: Automatically deploys on `main` branch pushes

### 10.2 Backend
- Repository: `/backend` (FastAPI)
- Deployment: Railway ($5-10/month for container + PostgreSQL)
- Environment variables: API keys (OddsAPI), database URL, JWT secret

### 10.3 Database
- PostgreSQL on Railway
- Automated backups
- ~$5-10/month for starter tier

### 10.4 Monitoring (Phase 1 MVP — optional)
- Simple logging to stdout (captured by Railway)
- Manual checks of background job logs via Railway dashboard
- No alerting required for MVP

---

## 11. Implementation Order (for reference to writing-plans skill)

1. **Database schema** — create tables, migrations
2. **Backend auth** — registration, login, JWT
3. **Odds ingestion** — OddsAPI integration + polling job
4. **Bet placement** — POST /bets endpoint
5. **Frontend scaffold** — Next.js + auth pages
6. **Odds display** — GET /odds endpoints + frontend component
7. **Active bets view** — display pending bets
8. **Score reconciliation** — ESPN integration + settlement logic
9. **History/P&L** — GET /bets/history endpoint + frontend page
10. **Testing & deployment** — E2E tests, deploy to Vercel + Railway

---

## 12. Future Phases (not detailed in Phase 1 spec)

### Phase 2: Backtesting & Trends
- Store all odds snapshots (not just latest)
- Build historical dataset for backtesting
- Add advanced stats (DVOA, FEI, etc.)
- Trend analysis tools
- Leaderboard

### Phase 3: Modeling & Contrarian Betting
- Predictive models (leveraging free sources like DVOA, KenPom)
- Counter-public-bias detection
- Model-vs-consensus comparison
- Recommended bets

---

## Notes & Decisions

- **Game ID:** ESPN IDs + home/away + start_time ensure uniqueness across seasons
- **Line locking:** Occurs at game_start_time, not bet placement, to avoid odds-movement gaming
- **Push handling:** Tracked as `push` status, returned stake (not counted as loss)
- **Reconciliation timing:** 6pm-5a Central Time hourly (covers typical game windows, avoids mid-day noise); retry on next hour if API fails
- **Odds storage:** Latest only (Phase 1); history added in Phase 2 for backtesting
- **No live bets:** Simplifies Phase 1, can be added later
- **No payment processing:** This MVP is for friends tracking bets. Real money settlement out of scope.
- **Bankroll tracking:** Users enter initial amount at signup; returns calculated as sum of payouts minus initial bankroll
- **Multiple bets per game:** Allowed — users can place multiple bets on same game from different sportsbooks
- **Custom bets:** Users can create alternate lines, props, or freeform bets without OddsAPI validation; manually marked as won/lost
- **Timezones:** All times (game_start_time, reconciliation schedule, etc.) in Central Time
