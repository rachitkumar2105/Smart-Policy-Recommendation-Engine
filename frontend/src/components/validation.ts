import type { RiskProfileRequest } from "../types/api";

// Mirrors the backend's Pydantic constraints (app/schemas.py RiskProfileRequest)
// so the form rejects the same inputs the API would reject with a 422.
export function validateProfile(
  profile: RiskProfileRequest,
): Partial<Record<keyof RiskProfileRequest, string>> {
  const errors: Partial<Record<keyof RiskProfileRequest, string>> = {};

  if (!profile.full_name || profile.full_name.trim().length === 0) {
    errors.full_name = "Full name is required";
  } else if (profile.full_name.length > 100) {
    errors.full_name = "Full name must be 100 characters or fewer";
  }

  if (!Number.isFinite(profile.age) || profile.age < 18 || profile.age > 100) {
    errors.age = "Age must be between 18 and 100";
  }

  if (!Number.isFinite(profile.monthly_income) || profile.monthly_income < 0) {
    errors.monthly_income = "Monthly income must be 0 or greater";
  }

  if (!Number.isFinite(profile.vehicle_value) || profile.vehicle_value < 0) {
    errors.vehicle_value = "Vehicle value must be 0 or greater";
  }

  if (!Number.isFinite(profile.property_value) || profile.property_value < 0) {
    errors.property_value = "Property value must be 0 or greater";
  }

  if (!Number.isFinite(profile.bmi) || profile.bmi < 10 || profile.bmi > 60) {
    errors.bmi = "BMI must be between 10 and 60";
  }

  if (
    !Number.isFinite(profile.children) ||
    profile.children < 0 ||
    profile.children > 10
  ) {
    errors.children = "Children must be between 0 and 10";
  }

  return errors;
}

export const isValid = (profile: RiskProfileRequest): boolean =>
  Object.keys(validateProfile(profile)).length === 0;
