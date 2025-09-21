import { useLocation, useNavigate } from "react-router-dom";

function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const prediction = location.state?.prediction;

  if (!prediction) {
    return (
      <div className="results">
        <h2>No prediction data found</h2>
        <button onClick={() => navigate("/")}>Go Back</button>
      </div>
    );
  }

  return (
    <div className="results">
      <h2>Prediction Results</h2>
      <p>
        <b>Final Score:</b> {prediction.final_score ?? "N/A"}
      </p>
      <p>
        <b>Margin of Error:</b> ±{prediction.margin_of_error ?? "N/A"}
      </p>
      <p>
        <b>Range:</b>{" "}
        {Array.isArray(prediction.range)
          ? `${prediction.range[0]} – ${prediction.range[1]}`
          : "N/A"}
      </p>

      <h3>Category Strengths</h3>
      <ul>
        {prediction.category_strengths &&
          Object.entries(prediction.category_strengths).map(([key, value]) => (
            <li key={key}>
              {key}: {value}
            </li>
          ))}
      </ul>

      <button onClick={() => navigate("/")}>Back to Home</button>
    </div>
  );
}

export default Results;
