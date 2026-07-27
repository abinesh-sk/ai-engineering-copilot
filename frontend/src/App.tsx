import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL;

type DashboardData = {
  total_traces: number;
  diagnosed_traces: number;
  message: string;
};

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/dashboard`)
      .then((res) => res.json())
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>AI Engineering Copilot</h1>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {data && (
        <div>
          <p>Total traces: {data.total_traces}</p>
          <p>Diagnosed traces: {data.diagnosed_traces}</p>
          <p>{data.message}</p>
        </div>
      )}
      {!data && !error && <p>Loading...</p>}
    </div>
  );
}

export default App;