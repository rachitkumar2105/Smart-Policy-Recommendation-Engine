import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ResultsView from "./ResultsView";
import type { RecommendationResponse } from "../types/api";

const MOCK_RESPONSE: RecommendationResponse = {
  customer_id: 1,
  recommendations: [
    {
      rank: 1,
      policy_id: 6,
      policy_name: "Comprehensive Auto Shield",
      policy_type: "AUTO",
      suitability_score: 83.0,
      final_premium: 1450.0,
      rule_based_adjustment: 0.0,
      ml_predicted_adjustment: 0.05,
      ml_predicted_charges: 8000,
      reasoning: "Vehicle ownership and value increased suitability.",
    },
  ],
};

describe("ResultsView", () => {
  it("renders recommendation cards from a mock API response", () => {
    render(<ResultsView data={MOCK_RESPONSE} />);
    expect(screen.getByTestId("results-view")).toBeInTheDocument();
    expect(screen.getByText(/Comprehensive Auto Shield/)).toBeInTheDocument();
    expect(screen.getByText(/₹1450\.00/)).toBeInTheDocument();
    expect(screen.getByTestId("rec-card")).toBeInTheDocument();
  });

  it("shows a no-results message for an empty recommendation list", () => {
    render(<ResultsView data={{ customer_id: 2, recommendations: [] }} />);
    expect(screen.getByTestId("no-results")).toBeInTheDocument();
  });

  it("renders the score chart when there are recommendations", () => {
    render(<ResultsView data={MOCK_RESPONSE} />);
    expect(screen.getByTestId("score-chart")).toBeInTheDocument();
  });
});
