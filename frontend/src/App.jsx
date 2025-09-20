import { useEffect, useState } from "react";
import axios from "axios";

function App() {
  const [status, setStatus] = useState("");
  const [course, setCourse] = useState("");
  const [grade, setGrade] = useState("");
  const [factors, setFactors] = useState("");
  const [professorId, setProfessorId] = useState("");
  const [result, setResult] = useState(null);

  // Health check on mount
  useEffect(() => {
    axios.get("http://127.0.0.1:8000/api/health/")
      .then(res => setStatus(res.data.status))
      .catch(() => setStatus("error"));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("http://127.0.0.1:8000/api/explain/", {
        course,
        predicted_grade: grade,
        factors: factors.split(","), // split by comma into list
        professor_id: parseInt(professorId)
      });
      setResult(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <h1>Grade Predictor</h1>
      <p>Backend status: {status}</p>

      <form onSubmit={handleSubmit}>
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
        <button type="submit">Predict</button>
      </form>

      {result && (
        <div>
          <h2>Explanation</h2>
          <p>{result.explanation}</p>

          {result.professor && !result.professor.error && (
            <div>
              <h2>Professor Info</h2>
              <p><b>Name:</b> {result.professor.name}</p>
              <p><b>Avg Rating:</b> {result.professor.avg_rating}</p>
              <p><b>Avg Difficulty:</b> {result.professor.avg_difficulty}</p>
              <p><b>Number of Ratings:</b> {result.professor.num_ratings}</p>
              <p><b>Would Take Again %:</b> {result.professor.would_take_again_percent}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
