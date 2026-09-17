import type { RecommendationItem } from "../types/api";

// Minimal hand-rolled SVG bar chart — avoids pulling in a charting library
// for a single, simple visualization (keeps the dependency footprint small).
export default function ScoreBarChart({ items }: { items: RecommendationItem[] }) {
  const width = 480;
  const barHeight = 28;
  const gap = 10;
  const height = items.length * (barHeight + gap);
  const maxScore = 100;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      role="img"
      aria-label="Suitability score comparison"
      data-testid="score-chart"
    >
      {items.map((item, i) => {
        const barWidth = (item.suitability_score / maxScore) * (width - 160);
        const y = i * (barHeight + gap);
        return (
          <g key={item.policy_id}>
            <text x={0} y={y + barHeight / 2 + 4} fontSize="12" fill="currentColor">
              {`#${item.rank} ${item.policy_name}`.slice(0, 22)}
            </text>
            <rect
              x={160}
              y={y}
              width={Math.max(barWidth, 2)}
              height={barHeight}
              fill="#4f8ef7"
              rx={4}
            />
            <text
              x={160 + barWidth + 6}
              y={y + barHeight / 2 + 4}
              fontSize="12"
              fill="currentColor"
            >
              {item.suitability_score.toFixed(1)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
