import { describe, expect, it } from "vitest";
import { validateProfile } from "./validation";
import type { RiskProfileRequest } from "../types/api";

const BASE: RiskProfileRequest = {
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

describe("validateProfile", () => {
  it("accepts a valid profile", () => {
    expect(validateProfile(BASE)).toEqual({});
  });

  it("rejects age below 18, mirroring backend ge=18", () => {
    const errors = validateProfile({ ...BASE, age: 17 });
    expect(errors.age).toBeDefined();
  });

  it("rejects age above 100, mirroring backend le=100", () => {
    const errors = validateProfile({ ...BASE, age: 200 });
    expect(errors.age).toBeDefined();
  });

  it("rejects negative monthly income, mirroring backend ge=0", () => {
    const errors = validateProfile({ ...BASE, monthly_income: -1 });
    expect(errors.monthly_income).toBeDefined();
  });

  it("rejects empty full name", () => {
    const errors = validateProfile({ ...BASE, full_name: "" });
    expect(errors.full_name).toBeDefined();
  });

  it("rejects bmi outside 10-60, mirroring backend ge=10 le=60", () => {
    expect(validateProfile({ ...BASE, bmi: 5 }).bmi).toBeDefined();
    expect(validateProfile({ ...BASE, bmi: 99 }).bmi).toBeDefined();
  });

  it("rejects negative vehicle/property values", () => {
    expect(validateProfile({ ...BASE, vehicle_value: -1 }).vehicle_value).toBeDefined();
    expect(
      validateProfile({ ...BASE, property_value: -1 }).property_value,
    ).toBeDefined();
  });
});
