import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

function Home() {
  const [professorId, setProfessorId] = useState("");
  const [canvasCourseId, setCanvasCourseId] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleFinalPrediction = async (e) => {
    e.preventDefault();
    setLoading(true);

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

      // navigate to results page with prediction data
      navigate("/results", { state: { prediction: res.data } });
    } catch (err) {
      console.error("Prediction error:", err.response?.data || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <h1 className="title">Grade Predictor</h1>

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
    </div>
  );
}

export default Home;
