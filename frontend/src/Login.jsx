import { useState } from "react";
import { login, loginAsGuardian } from "./api";

export default function Login({ onLoginSuccess }) {
  const [idCard, setIdCard] = useState("");
  const [step, setStep] = useState("initial"); // "initial" | "needs_guardian"
  const [minorName, setMinorName] = useState("");
  const [guardianIdCard, setGuardianIdCard] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleInitialSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(idCard);
      if (res.data.status === "minor_requires_guardian") {
        setMinorName(res.data.message);
        setStep("needs_guardian");
      } else if (res.data.status === "ok") {
        onLoginSuccess({ token: res.data.token, patient: res.data.patient });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGuardianSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await loginAsGuardian(idCard, guardianIdCard);
      onLoginSuccess({
        token: res.data.token,
        patient: res.data.patient,
        actingUser: res.data.acting_user,
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Verification failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Hospital Intake</h1>

        {step === "initial" && (
          <form onSubmit={handleInitialSubmit}>
            <label style={styles.label}>ID Card Number</label>
            <input
              style={styles.input}
              type="text"
              value={idCard}
              onChange={(e) => setIdCard(e.target.value)}
              placeholder="Enter your ID card number"
              required
            />
            <button style={styles.button} type="submit" disabled={loading}>
              {loading ? "Checking..." : "Continue"}
            </button>
          </form>
        )}

        {step === "needs_guardian" && (
          <form onSubmit={handleGuardianSubmit}>
            <p style={styles.notice}>{minorName}</p>
            <label style={styles.label}>Guardian's ID Card Number</label>
            <input
              style={styles.input}
              type="text"
              value={guardianIdCard}
              onChange={(e) => setGuardianIdCard(e.target.value)}
              placeholder="Enter guardian's ID card number"
              required
            />
            <button style={styles.button} type="submit" disabled={loading}>
              {loading ? "Verifying..." : "Confirm Guardian"}
            </button>
          </form>
        )}

        {error && <p style={styles.error}>{error}</p>}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    backgroundColor: "#f4f6f8",
  },
  card: {
    backgroundColor: "#fff",
    padding: "2.5rem",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
    width: "360px",
  },
  title: {
    marginBottom: "1.5rem",
    fontSize: "1.5rem",
    color: "#1a1a1a",
    textAlign: "center",
  },
  label: {
    display: "block",
    marginBottom: "0.4rem",
    fontSize: "0.9rem",
    color: "#444",
  },
  input: {
    width: "100%",
    padding: "0.7rem",
    marginBottom: "1rem",
    borderRadius: "8px",
    border: "1px solid #ccc",
    fontSize: "1rem",
    boxSizing: "border-box",
  },
  button: {
    width: "100%",
    padding: "0.8rem",
    borderRadius: "8px",
    border: "none",
    backgroundColor: "#2563eb",
    color: "#fff",
    fontSize: "1rem",
    cursor: "pointer",
  },
  notice: {
    backgroundColor: "#fff7e6",
    padding: "0.8rem",
    borderRadius: "8px",
    marginBottom: "1rem",
    fontSize: "0.9rem",
    color: "#7a5c00",
  },
  error: {
    color: "#d92d20",
    marginTop: "1rem",
    fontSize: "0.9rem",
    textAlign: "center",
  },
};