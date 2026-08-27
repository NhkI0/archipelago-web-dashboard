import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { getBasePath } from "./config";
import "./theme.css";

// "/" normally, "/<repo>/" for the GitHub Pages demo, or "/<uuid>/" for a hosted room.
const basename = getBasePath();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
