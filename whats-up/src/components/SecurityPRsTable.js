import React, { useState } from 'react';

function SecurityPRsTable({ prsData }) {
  const [sortBy, setSortBy] = useState('date');
  
  const securityPRs = prsData.filter(pr => pr.contribution_classification === 'security');
  
  const sortedPRs = [...securityPRs].sort((a, b) => {
    if (sortBy === 'date') {
      return new Date(b.created_at) - new Date(a.created_at);
    } else if (sortBy === 'repo') {
      return a.repository.localeCompare(b.repository);
    }
    return 0;
  });

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <section className="security-prs-table">
      <h2>Security Contributions</h2>
      <div className="table-controls">
        <label htmlFor="sort-select">Sort by: </label>
        <select 
          id="sort-select"
          value={sortBy} 
          onChange={(e) => setSortBy(e.target.value)}
        >
          <option value="date">Date</option>
          <option value="repo">Repository</option>
        </select>
      </div>
      <div className="table-responsive">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Repository</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {sortedPRs.map((pr) => (
              <tr key={pr.url}>
                <td>
                  <a href={pr.url} target="_blank" rel="noopener noreferrer">
                    {pr.title}
                  </a>
                </td>
                <td>{pr.repository}</td>
                <td>{formatDate(pr.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="table-footer">Total: {sortedPRs.length} security contributions</p>
    </section>
  );
}

export default SecurityPRsTable;
