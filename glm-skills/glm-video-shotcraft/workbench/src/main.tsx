import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Do not wrap in <React.StrictMode>: workbench always runs on dev server, StrictMode would mount every
// Remotion Player / thumbnail twice, causing visible flickering across dozen 1080p scenes.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
