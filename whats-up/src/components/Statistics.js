import React from 'react';

function Statistics({ prsData }) {
  const uniqueMembers = new Set(prsData.map(pr => pr.author)).size;
  const totalPRs = prsData.length;

  return (
    <section className="statistics">
      <h2>Team Statistics</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>{uniqueMembers}</h3>
          <p>Team Members</p>
        </div>
        <div className="stat-card">
          <h3>{totalPRs}</h3>
          <p>Total PRs</p>
        </div>
      </div>
    </section>
  );
}

export default Statistics;
