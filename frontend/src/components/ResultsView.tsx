import type { RecommendationResponse } from "../types/api";
import ScoreBarChart from "./ScoreBarChart";

export default function ResultsView({ data }: { data: RecommendationResponse }) {
  if (data.recommendations.length === 0) {
    return (
      <div data-testid="no-results">
        No policies matched your risk profile's eligibility criteria (age / income).
      </div>
    );
  }

  return (
    <div data-testid="results-view">
      <p>
        Generated {data.recommendations.length} recommendation(s) for customer #
        {data.customer_id}.
      </p>

      {data.recommendations.map((rec) => (
        <div className="rec-card" key={rec.policy_id} data-testid="rec-card">
          <h3>
            #{rec.rank} — {rec.policy_name} ({rec.policy_type})
          </h3>
          <div className="rec-grid">
            <div>
              <strong>Suitability score</strong>
              <div>{rec.suitability_score.toFixed(1)} / 100</div>
            </div>
            <div>
              <strong>Final premium</strong>
              <div>₹{rec.final_premium.toFixed(2)}</div>
            </div>
            <div>
              <strong>Rule-based adjustment</strong>
              <div>{(rec.rule_based_adjustment * 100).toFixed(1)}%</div>
            </div>
            <div>
              <strong>ML-predicted adjustment</strong>
              <div>{(rec.ml_predicted_adjustment * 100).toFixed(1)}%</div>
            </div>
          </div>
          <p className="reasoning">{rec.reasoning}</p>
        </div>
      ))}

      <h3>Suitability Comparison</h3>
      <ScoreBarChart items={data.recommendations} />
    </div>
  );
}
