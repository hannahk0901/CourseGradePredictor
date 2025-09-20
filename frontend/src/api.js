import axios from "axios";

// Point this to your Django backend
// If you run Django at localhost:8000, leave as-is
const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api",
});

export default api;
