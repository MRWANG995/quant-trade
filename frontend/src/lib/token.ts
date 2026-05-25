const TOKEN_KEY = "quant_trade_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

const MAX_AGE = 60 * 60 * 24 * 7;

export function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    document.cookie = `quant_trade_token=${encodeURIComponent(token)}; path=/; max-age=${MAX_AGE}; SameSite=Lax`;
  } else {
    localStorage.removeItem(TOKEN_KEY);
    document.cookie = "quant_trade_token=; path=/; max-age=0";
  }
}
