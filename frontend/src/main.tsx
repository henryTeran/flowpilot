import React from "react";
import ReactDOM from "react-dom/client";
import { SessionGate } from "./components/SessionGate";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SessionGate />
  </React.StrictMode>
);
