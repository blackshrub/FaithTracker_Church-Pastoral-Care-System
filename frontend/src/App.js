import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { IntegrationTest } from "@/components/IntegrationTest";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<IntegrationTest />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
