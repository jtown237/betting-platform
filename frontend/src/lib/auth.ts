const TOKEN_KEY = "auth_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const USER_ID_KEY = "user_id";

export interface TokenData {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
  userId?: number;
}

export const tokenManager = {
  getToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken: (tokenData: TokenData): void => {
    if (typeof window === "undefined") return;
    localStorage.setItem(TOKEN_KEY, tokenData.accessToken);
    if (tokenData.refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, tokenData.refreshToken);
    }
    if (tokenData.expiresAt) {
      localStorage.setItem("token_expires_at", tokenData.expiresAt.toString());
    }
    if (tokenData.userId) {
      localStorage.setItem(USER_ID_KEY, tokenData.userId.toString());
    }
  },

  getUserId: (): number | null => {
    if (typeof window === "undefined") return null;
    const userId = localStorage.getItem(USER_ID_KEY);
    return userId ? parseInt(userId, 10) : null;
  },

  removeToken: (): void => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem("token_expires_at");
    localStorage.removeItem(USER_ID_KEY);
  },

  getRefreshToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  isTokenExpired: (): boolean => {
    if (typeof window === "undefined") return true;
    const expiresAt = localStorage.getItem("token_expires_at");
    if (!expiresAt) return false;
    return Date.now() > parseInt(expiresAt, 10);
  },

  isAuthenticated: (): boolean => {
    const token = tokenManager.getToken();
    return !!token && !tokenManager.isTokenExpired();
  },
};
