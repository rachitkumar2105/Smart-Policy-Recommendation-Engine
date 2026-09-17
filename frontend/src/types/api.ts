// TypeScript mirrors of the backend's Pydantic schemas (backend/app/schemas.py).
// Keep in sync manually — the backend is the source of truth for validation.

export type Occupation = "DESK_JOB" | "HAZARDOUS" | "UNEMPLOYED";
export type Sex = "male" | "female";
export type Region = "northeast" | "northwest" | "southeast" | "southwest";

export interface RiskProfileRequest {
  full_name: string;
  age: number;
  monthly_income: number;
  occupation: Occupation;
  is_smoker: boolean;
  has_chronic_illness: boolean;
  owns_vehicle: boolean;
  vehicle_value: number;
  owns_property: boolean;
  property_value: number;
  sex: Sex;
  bmi: number;
  children: number;
  region: Region;
}

export interface RecommendationItem {
  rank: number;
  policy_id: number;
  policy_name: string;
  policy_type: string;
  suitability_score: number;
  final_premium: number;
  rule_based_adjustment: number;
  ml_predicted_adjustment: number;
  ml_predicted_charges: number;
  reasoning: string;
}

export interface RecommendationResponse {
  customer_id: number;
  recommendations: RecommendationItem[];
}

export interface PolicyOut {
  policy_id: number;
  policy_name: string;
  policy_type: string;
  description: string | null;
  base_premium: number;
  min_age: number;
  max_age: number;
  min_income: number;
  coverage_amount: number;
  is_active: boolean;
}

export interface ApiValidationError {
  detail: Array<{ type: string; loc: (string | number)[]; msg: string }>;
}
