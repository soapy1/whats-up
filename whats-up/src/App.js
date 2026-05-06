import React, { useState, useEffect } from 'react';
import './App.css';
import Statistics from './components/Statistics';
import ContributionSummary from './components/ContributionSummary';
import SecurityPRsTable from './components/SecurityPRsTable';

function App() {
  const [prsData, setPrsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPRs = async () => {
      try {
        const response = await fetch('../../prs.json');
        if (!response.ok) {
          throw new Error('Failed to load PR data');
        }
        const data = await response.json();
        setPrsData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPRs();
  }, []);

  if (loading) {
    return <div className="container"><p>Loading PR data...</p></div>;
  }

  if (error) {
    return <div className="container error"><p>Error: {error}</p></div>;
  }

  if (!prsData || prsData.length === 0) {
    return <div className="container"><p>No PR data available</p></div>;
  }

  return (
    <div className="App">
      <header className="app-header">
        <h1>Team Contributions Dashboard</h1>
        <p>Track open source contributions made by team members</p>
      </header>
      
      <main className="container">
        <Statistics prsData={prsData} />
        <ContributionSummary prsData={prsData} />
        <SecurityPRsTable prsData={prsData} />
      </main>
    </div>
  );
}

export default App;
