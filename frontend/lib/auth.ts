import Cookies from "js-cookie";
import { jwtDecode } from "jwt-decode";

const TOKEN_KEY = "cg_token";

interface JwtPayload {
  sub: string;
  exp: number;
}

export function saveToken(token: string): void {
  Cookies.set(TOKEN_KEY, token, { expires: 7, sameSite: "Lax" });
}

export function getToken(): string | null {
  return Cookies.get(TOKEN_KEY) ?? null;
}

export function removeToken(): void {
  Cookies.remove(TOKEN_KEY);
}

export function isTokenExpired(token: string): boolean {
  try {
    const { exp } = jwtDecode<JwtPayload>(token);
    return Date.now() / 1000 > exp;
  } catch {
    return true;
  }
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  return !isTokenExpired(token);
}
