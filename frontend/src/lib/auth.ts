const TOKEN_KEY = "auth_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export interface TokenData {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
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
  },

  removeToken: (): void => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem("token_expires_at");
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
