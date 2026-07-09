// src/main.jsx -- mount the presenter.
// No StrictMode: in dev it double-invokes effects, which would double-dispatch the
// replay timer / open a second EventSource (whose reconnect replays the log) and thus
// duplicate the accumulating callouts. The shipped build has no StrictMode anyway.
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(<App />);
