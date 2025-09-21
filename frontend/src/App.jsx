import { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css"; // <- CSS file for styling

// 🔹 Stable grade count-up (won't reset/glitch on re-renders)
function useStableGradeCountUp(target, duration = 2000) {
  const [value, setValue] = useState(0);
  const lastTargetRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const end = Number(target) || 0;

    // Only (re)start when the target actually changes
    if (lastTargetRef.current === end) return;
    lastTargetRef.current = end;

    cancelAnimationFrame(rafRef.current);
    let startTime = null;
    const startVal = 0;

    const step = (ts) => {
      if (!startTime) startTime = ts;
      const t = Math.min(1, (ts - startTime) / duration);
      const current = startVal + (end - startVal) * t;
      setValue(current);
      if (t < 1) rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return Math.round((value + Number.EPSILON) * 10) / 10; // one decimal
}

// 🔹 Generic count-up for bars (supports delay + proper cleanup)
function useCountUp(target, duration = 1500, delay = 0, trigger = null) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    if (trigger == null || target == null || isNaN(Number(target))) return;

    const end = Number(target);
    let startTime = null;

    const start = () => {
      const step = (ts) => {
        if (!startTime) startTime = ts;
        const t = Math.min(1, (ts - startTime) / duration);
        const current = end * t; // from 0 → end
        setValue(current);
        if (t < 1) {
          rafRef.current = requestAnimationFrame(step);
        }
      };
      rafRef.current = requestAnimationFrame(step);
    };

    timeoutRef.current = setTimeout(start, delay);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [trigger, duration, delay, target]);

  return Math.round((value + Number.EPSILON) * 10) / 10;
}

// 🔹 Reusable bar (animated fill + number)
function StrengthBar({ label, value, max = 100, delay = 0 }) {
  const animatedVal = useCountUp(value ?? 0, 1500, delay, value);
  const percent = Math.max(
    0,
    Math.min(100, max ? (animatedVal / max) * 100 : 0)
  );

  return (
    <div
      className="strength-bar fade-in"
      style={{ animationDelay: `${delay / 1000}s` }}
    >
      <span>{label}</span>
      <div className="bar">
        <div
          className="fill"
          style={{
            width: `${percent}%`,
            transition: `width 1.5s ease ${delay}ms`,
          }}
        >
          <span className="percent-text">
            {max === 5 ? `${animatedVal} / 5` : `${animatedVal}%`}
          </span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [professorId, setProfessorId] = useState("");
  const [canvasCourseId, setCanvasCourseId] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFinalPrediction = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPrediction(null); // hide results while loading

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

  const formatNumber = (num) => {
    if (num === null || num === undefined || isNaN(num)) return "N/A";
    return Math.round(num * 10) / 10;
  };

  // ✅ Stable grade animation: only restarts when final_score changes
  const animatedGrade = useStableGradeCountUp(prediction?.final_score ?? 0, 2000);

  return (
    <div className="app-container">
      <h1 className="app-title">iGradeU</h1>

      {/* Form */}
      <form className="prediction-form-inline" onSubmit={handleFinalPrediction}>
        <input
          type="text"
          value={professorId}
          onChange={(e) => setProfessorId(e.target.value)}
          placeholder="Professor ID"
          required
        />
        <input
          type="text"
          value={canvasCourseId}
          onChange={(e) => setCanvasCourseId(e.target.value)}
          placeholder="Canvas Course ID"
          required
        />
        <input
          type="text"
          value={syllabus}
          onChange={(e) => setSyllabus(e.target.value)}
          placeholder="Paste syllabus here..."
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "⏳" : "🔮"}
        </button>
      </form>

      {prediction && (
        <div className="results">
          <h2 className="fade-in" style={{ animationDelay: "0s" }}>
            📊 Prediction Results
          </h2>

          {/* 🔹 Animated grade (stable) */}
          <div
            className="score-highlight fade-in"
            style={{ animationDelay: "0.5s" }}
          >
            {animatedGrade}%
          </div>

          {/* 🔹 Margin + Range */}
          <div
            className="metrics-inline fade-in"
            style={{ animationDelay: "1s" }}
          >
            <div className="gradient-text">
              <b>Margin of Error:</b> ±{prediction.margin_of_error ?? "N/A"}
            </div>
            <div className="gradient-text">
              <b>Range:</b>{" "}
              {Array.isArray(prediction.range)
                ? `${formatNumber(prediction.range[0])} – ${formatNumber(
                    prediction.range[1]
                  )}`
                : "N/A"}
            </div>
          </div>

          {/* 🔹 Strength Metrics */}
          <div className="fade-in" style={{ animationDelay: "1.5s" }}>
            <h3> Your Strength Score</h3>
            <div className="strengths">
              <StrengthBar
                label="Overall Strength"
                value={prediction.overall_strength}
                delay={0}
              />
              <StrengthBar
                label="Punctual Strength"
                value={prediction.punctual_strength}
                delay={400}
              />
            </div>
          </div>

          {/* 🔹 Category Strengths */}
          <div className="fade-in" style={{ animationDelay: "2s" }}>
            <h3>Your Category Strength Score</h3>
            <div className="strengths">
              {Object.entries(prediction.category_strengths || {}).map(
                ([key, value], idx) => (
                  <StrengthBar
                    key={key}
                    label={key}
                    value={value}
                    delay={idx * 400}
                  />
                )
              )}
            </div>
          </div>

          {/* 🔹 Course Weights */}
          <div className="fade-in" style={{ animationDelay: "2.5s" }}>
            <h3>
              {prediction.course_name
                ? `${prediction.course_name} Weight Score`
                : "Course Weights"}
            </h3>

            <div className="strengths">
              {[
                { label: "Projects", value: prediction.projects },
                { label: "Assignments", value: prediction.assignments },
                { label: "Exams", value: prediction.exams },
                { label: "Participation", value: prediction.participation },
              ].map(({ label, value }, idx) => (
                <StrengthBar
                  key={label}
                  label={label}
                  value={value}
                  delay={idx * 400}
                />
              ))}
            </div>
          </div>


          {/* 🔹 Professor Difficulty */}
          {prediction.rmp && (
            <div className="fade-in" style={{ animationDelay: "3s" }}>
              <h3>Class Difficulty Scores</h3>
              <div className="strengths">
                <StrengthBar
                  label="Difficulty"
                  value={prediction.rmp.avg_difficulty}
                  max={5}
                  delay={0}
                />
                <StrengthBar
                  label="Would Take Again"
                  value={prediction.rmp.would_take_again_percent}
                  delay={400}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
