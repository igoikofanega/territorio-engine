import "./index.css";

import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import Movimiento from "./components/Movimiento";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Movimiento>
      <App />
    </Movimiento>
  </React.StrictMode>,
);
