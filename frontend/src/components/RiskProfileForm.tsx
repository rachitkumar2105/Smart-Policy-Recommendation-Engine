import { useState } from "react";
import type { RiskProfileRequest } from "../types/api";
import { validateProfile } from "./validation";

const DEFAULT_PROFILE: RiskProfileRequest = {
  full_name: "Jane Doe",
  age: 30,
  monthly_income: 50000,
  occupation: "DESK_JOB",
  is_smoker: false,
  has_chronic_illness: false,
  owns_vehicle: false,
  vehicle_value: 0,
  owns_property: false,
  property_value: 0,
  sex: "male",
  bmi: 25,
  children: 0,
  region: "southeast",
};

interface Props {
  onSubmit: (profile: RiskProfileRequest) => void;
  submitting: boolean;
}

export default function RiskProfileForm({ onSubmit, submitting }: Props) {
  const [profile, setProfile] = useState<RiskProfileRequest>(DEFAULT_PROFILE);
  const [touched, setTouched] = useState(false);

  const errors = validateProfile(profile);
  const hasErrors = Object.keys(errors).length > 0;

  function update<K extends keyof RiskProfileRequest>(
    key: K,
    value: RiskProfileRequest[K],
  ) {
    setProfile((p) => ({ ...p, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!hasErrors) onSubmit(profile);
  }

  return (
    <form onSubmit={handleSubmit} className="risk-form" data-testid="risk-form">
      <h2>Your Risk Profile</h2>

      <label>
        Full name
        <input
          value={profile.full_name}
          onChange={(e) => update("full_name", e.target.value)}
        />
        {touched && errors.full_name && <span className="err">{errors.full_name}</span>}
      </label>

      <label>
        Age
        <input
          type="number"
          value={profile.age}
          onChange={(e) => update("age", Number(e.target.value))}
        />
        {touched && errors.age && <span className="err">{errors.age}</span>}
      </label>

      <label>
        Monthly income
        <input
          type="number"
          value={profile.monthly_income}
          onChange={(e) => update("monthly_income", Number(e.target.value))}
        />
        {touched && errors.monthly_income && (
          <span className="err">{errors.monthly_income}</span>
        )}
      </label>

      <label>
        Occupation
        <select
          value={profile.occupation}
          onChange={(e) =>
            update("occupation", e.target.value as RiskProfileRequest["occupation"])
          }
        >
          <option value="DESK_JOB">Desk job</option>
          <option value="HAZARDOUS">Hazardous</option>
          <option value="UNEMPLOYED">Unemployed</option>
        </select>
      </label>

      <label>
        Sex
        <select
          value={profile.sex}
          onChange={(e) => update("sex", e.target.value as RiskProfileRequest["sex"])}
        >
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </label>

      <label>
        BMI
        <input
          type="number"
          step="0.1"
          value={profile.bmi}
          onChange={(e) => update("bmi", Number(e.target.value))}
        />
        {touched && errors.bmi && <span className="err">{errors.bmi}</span>}
      </label>

      <label>
        Children
        <input
          type="number"
          value={profile.children}
          onChange={(e) => update("children", Number(e.target.value))}
        />
        {touched && errors.children && <span className="err">{errors.children}</span>}
      </label>

      <label>
        Region
        <select
          value={profile.region}
          onChange={(e) =>
            update("region", e.target.value as RiskProfileRequest["region"])
          }
        >
          <option value="northeast">Northeast</option>
          <option value="northwest">Northwest</option>
          <option value="southeast">Southeast</option>
          <option value="southwest">Southwest</option>
        </select>
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={profile.is_smoker}
          onChange={(e) => update("is_smoker", e.target.checked)}
        />
        Smoker
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={profile.has_chronic_illness}
          onChange={(e) => update("has_chronic_illness", e.target.checked)}
        />
        Has a chronic illness
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={profile.owns_vehicle}
          onChange={(e) => update("owns_vehicle", e.target.checked)}
        />
        Owns a vehicle
      </label>

      <label>
        Vehicle value
        <input
          type="number"
          disabled={!profile.owns_vehicle}
          value={profile.vehicle_value}
          onChange={(e) => update("vehicle_value", Number(e.target.value))}
        />
        {touched && errors.vehicle_value && (
          <span className="err">{errors.vehicle_value}</span>
        )}
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={profile.owns_property}
          onChange={(e) => update("owns_property", e.target.checked)}
        />
        Owns property
      </label>

      <label>
        Property value
        <input
          type="number"
          disabled={!profile.owns_property}
          value={profile.property_value}
          onChange={(e) => update("property_value", Number(e.target.value))}
        />
        {touched && errors.property_value && (
          <span className="err">{errors.property_value}</span>
        )}
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? "Scoring..." : "Get Recommendations"}
      </button>
    </form>
  );
}
