import { useState } from "react";
import axios from "axios";
import "./App.css"; // <- CSS file for styling

function App() {
  const [professorId, setProfessorId] = useState("");
  const [canvasCourseId, setCanvasCourseId] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("ok"); // optional backend check

  const handleFinalPrediction = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPrediction(null);

    try {
      const payload = {
        syllabus_text: syllabus,
        professor_id: professorId ? parseInt(professorId) : null,
        canvas_course_id: canvasCourseId ? parseInt(canvasCourseId) : null,
      };

      const res = await axios.post(
        "http://127.0.0.1:8000/api/predict-grade/",
        payload
      );
      setPrediction(res.data);
    } catch (err) {
      console.error("Prediction error:", err.response?.data || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <h1 className="title">Grade Predictor</h1>
      <p className="status">Backend status: {status}</p>

      <form className="prediction-form" onSubmit={handleFinalPrediction}>
        <input
          type="text"
          placeholder="Professor ID (RateMyProfessor)"
          value={professorId}
          onChange={(e) => setProfessorId(e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="Canvas Course ID"
          value={canvasCourseId}
          onChange={(e) => setCanvasCourseId(e.target.value)}
          required
        />
        <textarea
          placeholder="Paste syllabus text..."
          rows={6}
          value={syllabus}
          onChange={(e) => setSyllabus(e.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "Calculating..." : "Predict Grade"}
        </button>
      </form>

      {prediction && (
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
              Object.entries(prediction.category_strengths).map(
                ([key, value]) => (
                  <li key={key}>
                    {key}: {value}
                  </li>
                )
              )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;
