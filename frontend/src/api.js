import axios from "axios";

const API_BASE_URL = "https://thepitt.onrender.com";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export const login = (idCardNumber) =>
  api.post("/auth/login", { id_card_number: idCardNumber });

export const loginAsGuardian = (minorIdCard, guardianIdCard) =>
  api.post("/auth/login-as-guardian", {
    minor_id_card: minorIdCard,
    guardian_id_card: guardianIdCard,
  });

export const startChat = (token) => api.post("/chat/start", { token });

export const getCategories = () => api.get("/chat/categories");

export const sendMessage = (sessionId, message, category = null) =>
  api.post("/chat/message", { session_id: sessionId, message, category });

export const goBack = (sessionId) => api.post("/chat/back", { session_id: sessionId });

export default api;