import { useState } from "react";
import Login from "./Login";
import Chat from "./Chat";

function App() {
  const [session, setSession] = useState(null);

  if (!session) {
    return <Login onLoginSuccess={setSession} />;
  }

  return <Chat session={session} />;
}

export default App;