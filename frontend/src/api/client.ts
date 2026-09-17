import type {
  PolicyOut,
  RecommendationResponse,
  RiskProfileRequest,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}

export function submitRiskProfile(
  payload: RiskProfileRequest,
): Promise<RecommendationResponse> {
  return request<RecommendationResponse>("/api/v1/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchPolicies(): Promise<PolicyOut[]> {
  return request<PolicyOut[]>("/api/v1/policies");
}
