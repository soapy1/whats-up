import React, { useState, useEffect } from 'react';
import './App.css';
import Statistics from './components/Statistics';
import ContributionSummary from './components/ContributionSummary';
import SecurityPRsTable from './components/SecurityPRsTable';
import DateRangeFilter from './components/DateRangeFilter';

function App() {
  const [prsData, setPrsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);

  useEffect(() => {
    const fetchPRs = async () => {
      try {
        const response = await fetch('/prs.json');
        if (!response.ok) {
          throw new Error('Failed to load PR data');
        }
        const data = await response.json();
        setPrsData(data);
        
        // Set default dates: end date = today, start date = 30 days ago
        const today = new Date();
        const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
        setEndDate(today.toISOString().split('T')[0]);
        setStartDate(thirtyDaysAgo.toISOString().split('T')[0]);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPRs();
  }, []);

  const filteredPRs = prsData
    ? prsData.filter((pr) => {
        const prDate = new Date(pr.created_at);
        const start = new Date(startDate);
        const end = new Date(endDate);
        return prDate >= start && prDate <= end;
      })
    : [];

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
        <DateRangeFilter 
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
        />
        <Statistics prsData={filteredPRs} />
        <ContributionSummary prsData={filteredPRs} />
        <SecurityPRsTable prsData={filteredPRs} />
      </main>
    </div>
  );
}

export default App;
