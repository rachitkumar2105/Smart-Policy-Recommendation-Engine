import { useState } from "react";
import RiskProfileForm from "./components/RiskProfileForm";
import ResultsView from "./components/ResultsView";
import { submitRiskProfile, ApiError } from "./api/client";
import type { RecommendationResponse, RiskProfileRequest } from "./types/api";
import "./App.css";

export default function App() {
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(profile: RiskProfileRequest) {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const data = await submitRiskProfile(profile);
      setResult(data);
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        setError("Rate limit exceeded. Please wait a moment and try again.");
      } else if (e instanceof ApiError && e.status === 422) {
        setError("The backend rejected the request as invalid.");
      } else {
        setError("Could not reach the backend.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app">
      <h1>🛡️ Smart Policy Recommendation Engine</h1>
      <p className="subtitle">
        Simulates an insurance underwriting workflow: submit a risk profile and get
        ranked, explainable policy recommendations with a hybrid rule-based + ML
        risk-adjusted premium.
      </p>

      <RiskProfileForm onSubmit={handleSubmit} submitting={submitting} />

      {error && (
        <div className="error" data-testid="error-banner">
          {error}
        </div>
      )}
      {result && <ResultsView data={result} />}
    </div>
  );
}
