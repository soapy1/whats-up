import React, { useState } from 'react';

function SecurityPRsTable({ prsData }) {
  const SECURITY_CLASSIFICATIONS = [
    'security fix',
    'cve patch',
    'vulnerability fix',
    'exploit mitigation',
    'security enhancement',
  ];

  const securityPRs = prsData.filter(pr =>
    SECURITY_CLASSIFICATIONS.includes(pr.contribution_classification)
  );

  const [sortConfig, setSortConfig] = useState({
    key: 'created_at',
    direction: 'desc',
  });

  const sortedPRs = [...securityPRs].sort((a, b) => {
    let aValue = a[sortConfig.key];
    let bValue = b[sortConfig.key];

    if (sortConfig.key === 'created_at') {
      aValue = new Date(aValue);
      bValue = new Date(bValue);
    }

    if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
    return 0;
  });

  const handleSort = (key) => {
    setSortConfig({
      key,
      direction:
        sortConfig.key === key && sortConfig.direction === 'asc'
          ? 'desc'
          : 'asc',
    });
  };

  return (
    <section className="security-prs">
      <h2>Security-Related PRs</h2>
      {securityPRs.length === 0 ? (
        <p>No security-related PRs found</p>
      ) : (
        <div className="table-wrapper">
          <table className="prs-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('title')}>
                  Title {sortConfig.key === 'title' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </th>
                <th onClick={() => handleSort('repository')}>
                  Repository {sortConfig.key === 'repository' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </th>
                <th onClick={() => handleSort('contribution_classification')}>
                  Classification {sortConfig.key === 'contribution_classification' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </th>
                <th onClick={() => handleSort('created_at')}>
                  Created {sortConfig.key === 'created_at' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </th>
                <th>Link</th>
              </tr>
            </thead>
            <tbody>
              {sortedPRs.map((pr, index) => (
                <tr key={index}>
                  <td className="pr-title">{pr.title}</td>
                  <td>{pr.repository}</td>
                  <td>
                    <span className={`badge badge-${pr.contribution_classification.replace(/\s+/g, '-')}`}>
                      {pr.contribution_classification}
                    </span>
                  </td>
                  <td>{new Date(pr.created_at).toLocaleDateString()}</td>
                  <td>
                    <a href={pr.url} target="_blank" rel="noopener noreferrer">
                      View PR
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default SecurityPRsTable;
