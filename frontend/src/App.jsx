import { useEffect, useState } from "react";
import axios from "axios";

function App() {
  const [status, setStatus] = useState("");

  // --- Existing state for /api/explain ---
  const [course, setCourse] = useState("");
  const [grade, setGrade] = useState("");
  const [factors, setFactors] = useState("");
  const [professorId, setProfessorId] = useState("");
  const [result, setResult] = useState(null);

  // --- Canvas ---
  const [courseId, setCourseId] = useState(""); // single course
  const [canvasGrades, setCanvasGrades] = useState(null);
  const [allCanvasData, setAllCanvasData] = useState(null);
  const [loadingCourse, setLoadingCourse] = useState(false);
  const [loadingAllCourses, setLoadingAllCourses] = useState(false);

  // --- New state for /api/predict-grade ---
  const [predictCourseId, setPredictCourseId] = useState("");
  const [predictProfessorId, setPredictProfessorId] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [loadingPrediction, setLoadingPrediction] = useState(false);

  // Health check
  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/api/health/")
      .then((res) => setStatus(res.data.status))
      .catch(() => setStatus("error"));
  }, []);

  // --- Existing explain_prediction ---
  const handlePredictSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("http://127.0.0.1:8000/api/explain/", {
        course,
        predicted_grade: grade,
        factors: factors.split(","),
        professor_id: professorId ? parseInt(professorId) : null,
      });
      setResult(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  // --- New predict_grade ---
  const handleFinalPrediction = async (e) => {
    e.preventDefault();
    setLoadingPrediction(true);
    setPrediction(null);

    try {
      const payload = {
        syllabus_text: syllabus,
        student_factors: ["Strong GPA", "Good at projects"], // placeholder
      };
      if (predictCourseId) payload.canvas_course_id = parseInt(predictCourseId);
      if (predictProfessorId)
        payload.professor_id = parseInt(predictProfessorId);

      const res = await axios.post(
        "http://127.0.0.1:8000/api/predict-grade/",
        payload
      );
      console.log("Prediction API response:", res.data);

      // ✅ store the whole response, not just res.data.prediction
      setPrediction(res.data);
    } catch (err) {
      console.error("Prediction error:", err.response?.data || err.message);
    } finally {
      setLoadingPrediction(false);
    }
  };

  // --- Canvas (single course + all courses) ---
  const handleCanvasSubmit = async (e) => {
    e.preventDefault();
    setLoadingCourse(true);
    setCanvasGrades(null);
    try {
      const res = await axios.get(
        `http://127.0.0.1:8000/api/canvas/${courseId}/grades/`
      );
      setCanvasGrades(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingCourse(false);
    }
  };

  const handleFetchAllCourses = async () => {
    setLoadingAllCourses(true);
    setAllCanvasData(null);
    try {
      const res = await axios.get("http://127.0.0.1:8000/api/canvas/all-data");
      setAllCanvasData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAllCourses(false);
    }
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "Arial, sans-serif" }}>
      <h1>Grade Predictor</h1>
      <p>Backend status: {status}</p>

      {/* ===================== EXPLAIN PREDICTION ===================== */}
      <h2>Explain Prediction (demo)</h2>
      <form onSubmit={handlePredictSubmit} style={{ marginBottom: "2rem" }}>
        <input
          type="text"
          placeholder="Course (e.g. CS1530)"
          value={course}
          onChange={(e) => setCourse(e.target.value)}
        />
        <input
          type="text"
          placeholder="Predicted Grade (e.g. B+)"
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
        />
        <input
          type="text"
          placeholder="Factors (comma-separated)"
          value={factors}
          onChange={(e) => setFactors(e.target.value)}
        />
        <input
          type="text"
          placeholder="Professor ID (e.g. 2936635)"
          value={professorId}
          onChange={(e) => setProfessorId(e.target.value)}
        />
        <button type="submit">Explain</button>
      </form>

      {result && (
        <div>
          <h3>Explanation</h3>
          <p>{result.explanation}</p>
          {result.professor && !result.professor.error && (
            <div>
              <h3>Professor Info</h3>
              <p>
                <b>Name:</b> {result.professor.name}
              </p>
              <p>
                <b>Avg Rating:</b> {result.professor.avg_rating}
              </p>
              <p>
                <b>Avg Difficulty:</b> {result.professor.avg_difficulty}
              </p>
              <p>
                <b>Number of Ratings:</b> {result.professor.num_ratings}
              </p>
              <p>
                <b>Would Take Again %:</b>{" "}
                {result.professor.would_take_again_percent}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ===================== FINAL PREDICTION ===================== */}
      <h2>Final Grade Prediction</h2>
      <form onSubmit={handleFinalPrediction} style={{ marginBottom: "2rem" }}>
        <input
          type="text"
          placeholder="Canvas Course ID"
          value={predictCourseId}
          onChange={(e) => setPredictCourseId(e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="Professor ID"
          value={predictProfessorId}
          onChange={(e) => setPredictProfessorId(e.target.value)}
        />
        <textarea
          placeholder="Paste syllabus text..."
          rows={4}
          value={syllabus}
          onChange={(e) => setSyllabus(e.target.value)}
          required
        />
        <button type="submit" disabled={loadingPrediction}>
          {loadingPrediction ? "Calculating..." : "Predict Grade"}
        </button>
      </form>

      {prediction && (
        <div>
          <h3>Prediction Results</h3>
          <p>
            <b>Final Score:</b> {prediction.final_score ?? "N/A"}
          </p>
          <p>
            <b>Margin of Error:</b> ±{prediction.margin_of_error ?? "N/A"}
          </p>
          <p>
            <b>Range:</b>{" "}
            {prediction.range
              ? `${prediction.range[0]} – ${prediction.range[1]}`
              : "N/A"}
          </p>

          <h4>Category Strengths</h4>
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

      {/* ===================== CANVAS: SINGLE COURSE ===================== */}
      <h2>View Canvas Grades (Single Course)</h2>
      <form onSubmit={handleCanvasSubmit}>
        <input
          type="text"
          placeholder="Enter Canvas Course ID (e.g. 237176)"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
        />
        <button type="submit">Fetch Grades</button>
      </form>

      {loadingCourse && <p>Loading course grades...</p>}
      {canvasGrades && (
        <div style={{ marginTop: "2rem" }}>
          <h3>
            Course: {canvasGrades.course?.name} (
            {canvasGrades.course?.course_code})
          </h3>
          {canvasGrades.categories.map((cat, i) => (
            <div key={i} style={{ marginBottom: "1rem" }}>
              <h4>{cat.category}</h4>
              <p>
                <b>Weight:</b> {cat.weight || 0}% |{" "}
                <b>Percent:</b>{" "}
                {cat.percent !== null
                  ? `${cat.percent.toFixed(2)}%`
                  : "No grades yet"}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ===================== CANVAS: ALL COURSES ===================== */}
      <h2>All Canvas Data</h2>
      <button onClick={handleFetchAllCourses}>
        Show User’s Complete Canvas Data
      </button>

      {loadingAllCourses && <p>Loading all courses...</p>}
      {allCanvasData &&
        allCanvasData.map((course, idx) => (
          <div key={idx} style={{ marginTop: "2rem" }}>
            <h3>
              Course: {course.course?.name || `Course ${course.course?.id}`} (
              {course.course?.course_code || course.course?.id})
            </h3>

            {course.course?.final_grade && (
              <p>
                <b>Final Grade:</b> {course.course.final_grade} (
                {course.course.final_score}%)
              </p>
            )}

            {course.categories &&
              course.categories.map((cat, i) => (
                <div key={i} style={{ marginBottom: "1rem" }}>
                  <h4>{cat.category}</h4>
                  <p>
                    <b>Weight:</b> {cat.weight || 0}% |{" "}
                    <b>Percent:</b>{" "}
                    {cat.percent !== null
                      ? `${cat.percent.toFixed(2)}%`
                      : "No grades yet"}
                  </p>

                  {cat.assignments && cat.assignments.length > 0 ? (
                    <ul>
                      {cat.assignments.map((a) => (
                        <li key={a.id}>
                          <a
                            href={a.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {a.name}
                          </a>{" "}
                          - {a.score !== null ? a.score : "N/A"} /{" "}
                          {a.points_possible}{" "}
                          {a.late ? "(Late)" : ""}
                          {a.excused ? " (Excused)" : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No assignments yet.</p>
                  )}
                </div>
              ))}
          </div>
        ))}
    </div>
  );
}

export default App;
