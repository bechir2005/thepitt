import { useState, useEffect, useRef } from "react";
import { startChat, sendMessage, getCategories, goBack } from "./api";

export default function Chat({ session, onRestart }) {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [finished, setFinished] = useState(false);
  const [appointment, setAppointment] = useState(null);
  const [allergyWarning, setAllergyWarning] = useState(null);
  const [categories, setCategories] = useState([]);
  const [categoryChosen, setCategoryChosen] = useState(false);
  const [canGoBack, setCanGoBack] = useState(false);
  const bottomRef = useRef(null);

  const initSession = async () => {
    setLoading(true);
    setFinished(false);
    setAppointment(null);
    setAllergyWarning(null);
    setCategoryChosen(false);
    setCanGoBack(false);
    try {
      const [chatRes, catRes] = await Promise.all([
        startChat(session.token),
        getCategories(),
      ]);
      setSessionId(chatRes.data.session_id);
      setMessages([{ role: "assistant", text: chatRes.data.message }]);
      setCategories(catRes.data.categories);
    } catch (err) {
      setMessages([
        { role: "assistant", text: "Sorry, something went wrong starting the session." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleCategoryClick = async (category, label) => {
    setMessages((prev) => [...prev, { role: "user", text: label }]);
    setCategoryChosen(true);
    setLoading(true);
    try {
      const res = await sendMessage(sessionId, label, category);
      const data = res.data;
      setMessages((prev) => [...prev, { role: "assistant", text: data.message }]);
      setCanGoBack(false); // just started the tree, nothing to go back to yet
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || finished) return;

    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendMessage(sessionId, userMessage);
      const data = res.data;

      setMessages((prev) => [...prev, { role: "assistant", text: data.message }]);
      setCanGoBack(true);

      if (data.allergy_warning) {
        setAllergyWarning(data.allergy_warning);
      }

      if (data.finished) {
        setFinished(true);
        setCanGoBack(false);
        if (data.appointment) {
          setAppointment(data.appointment);
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = async () => {
    setLoading(true);
    try {
      const res = await goBack(sessionId);
      const data = res.data;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "↩️ " + data.message },
      ]);
      setCanGoBack(data.can_go_back);
      if (data.category_reset) {
        // Backend actually cleared the category — show the picker again
        setCategoryChosen(false);
      }
    } catch (err) {
      // silently ignore — back is a convenience feature
    } finally {
      setLoading(false);
    }
  };

  const handleRestart = () => {
    initSession();
  };

  const showCategoryPicker = !categoryChosen && !finished && !loading;

  return (
    <div style={styles.container}>
      <div style={styles.chatBox}>
        <div style={styles.header}>
          <div>
            Hospital Intake Assistant
            {session.patient.is_minor && session.actingUser && (
              <div style={styles.subheader}>
                On behalf of {session.patient.first_name} ({session.actingUser.first_name} logged in)
              </div>
            )}
          </div>
          <button style={styles.restartButton} onClick={handleRestart} title="Start over">
            ⟳ Restart
          </button>
        </div>

        {allergyWarning && <div style={styles.allergyBanner}>{allergyWarning}</div>}

        <div style={styles.messages}>
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                ...styles.bubble,
                ...(msg.role === "user" ? styles.userBubble : styles.assistantBubble),
              }}
            >
              {msg.text}
            </div>
          ))}

          {showCategoryPicker && (
            <div style={styles.categoryGrid}>
              {categories.map((c) => (
                <button
                  key={c.category}
                  style={styles.categoryButton}
                  onClick={() => handleCategoryClick(c.category, c.label)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          )}

          {loading && <div style={styles.typingIndicator}>...</div>}
          <div ref={bottomRef} />
        </div>

        {appointment && (
          <div style={styles.appointmentCard}>
            <strong>Appointment Confirmed</strong>
            <div>{appointment.doctor} — {appointment.department}</div>
            <div>{new Date(appointment.start_time).toLocaleString()}</div>
          </div>
        )}

        {!finished ? (
          <form onSubmit={handleSend} style={styles.inputRow}>
            {categoryChosen && (
              <button
                type="button"
                style={styles.backButton}
                onClick={handleBack}
                disabled={loading}
                title="Go back to previous question"
              >
                ← Back
              </button>
            )}
            <input
              style={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                categoryChosen ? "Type your message..." : "Pick a category above, or describe it here..."
              }
              disabled={loading}
            />
            <button style={styles.sendButton} type="submit" disabled={loading}>
              Send
            </button>
          </form>
        ) : (
          <div style={styles.finishedNotice}>
            Session complete.
            <button style={styles.restartLink} onClick={handleRestart}>
              Start a new visit
            </button>
          </div>
        )}
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
  chatBox: {
    width: "440px",
    height: "640px",
    backgroundColor: "#fff",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    padding: "1rem",
    backgroundColor: "#2563eb",
    color: "#fff",
    fontWeight: "bold",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  subheader: {
    fontSize: "0.8rem",
    fontWeight: "normal",
    marginTop: "0.25rem",
    opacity: 0.9,
  },
  restartButton: {
    background: "rgba(255,255,255,0.15)",
    border: "1px solid rgba(255,255,255,0.4)",
    color: "#fff",
    borderRadius: "6px",
    padding: "0.3rem 0.6rem",
    fontSize: "0.8rem",
    cursor: "pointer",
  },
  allergyBanner: {
    backgroundColor: "#fff1f0",
    color: "#a8071a",
    padding: "0.6rem 1rem",
    fontSize: "0.85rem",
    borderBottom: "1px solid #ffccc7",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.6rem",
  },
  bubble: {
    maxWidth: "75%",
    padding: "0.6rem 0.9rem",
    borderRadius: "14px",
    fontSize: "0.95rem",
    lineHeight: 1.4,
  },
  assistantBubble: {
    backgroundColor: "#f0f2f5",
    color: "#1a1a1a",
    alignSelf: "flex-start",
  },
  userBubble: {
    backgroundColor: "#2563eb",
    color: "#fff",
    alignSelf: "flex-end",
  },
  typingIndicator: {
    alignSelf: "flex-start",
    color: "#999",
    fontStyle: "italic",
    fontSize: "0.85rem",
  },
  categoryGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0.5rem",
    marginTop: "0.4rem",
  },
  categoryButton: {
    padding: "0.6rem 0.5rem",
    borderRadius: "10px",
    border: "1px solid #d0d7de",
    backgroundColor: "#fff",
    color: "#2563eb",
    fontSize: "0.85rem",
    cursor: "pointer",
    textAlign: "left",
  },
  appointmentCard: {
    margin: "0 1rem 1rem 1rem",
    padding: "0.8rem",
    backgroundColor: "#f6ffed",
    border: "1px solid #b7eb8f",
    borderRadius: "8px",
    fontSize: "0.9rem",
  },
  inputRow: {
    display: "flex",
    padding: "0.75rem",
    borderTop: "1px solid #eee",
    gap: "0.5rem",
    alignItems: "center",
  },
  backButton: {
    padding: "0.6rem 0.7rem",
    borderRadius: "8px",
    border: "1px solid #d0d7de",
    backgroundColor: "#fafafa",
    color: "#444",
    cursor: "pointer",
    fontSize: "0.85rem",
    whiteSpace: "nowrap",
  },
  input: {
    flex: 1,
    padding: "0.6rem",
    borderRadius: "8px",
    border: "1px solid #ccc",
    fontSize: "0.95rem",
  },
  sendButton: {
    padding: "0.6rem 1.2rem",
    borderRadius: "8px",
    border: "none",
    backgroundColor: "#2563eb",
    color: "#fff",
    cursor: "pointer",
  },
  finishedNotice: {
    padding: "1rem",
    textAlign: "center",
    color: "#888",
    borderTop: "1px solid #eee",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
    alignItems: "center",
  },
  restartLink: {
    background: "none",
    border: "none",
    color: "#2563eb",
    cursor: "pointer",
    fontSize: "0.9rem",
    textDecoration: "underline",
  },
};