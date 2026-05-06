import React from 'react';

function ContributionSummary({ prsData }) {
  const SECURITY_CLASSIFICATIONS = [
    'security fix',
    'cve patch',
    'vulnerability fix',
    'exploit mitigation',
    'security enhancement',
  ];

  const classificationCounts = prsData.reduce((acc, pr) => {
    const classification = pr.contribution_classification;
    acc[classification] = (acc[classification] || 0) + 1;
    return acc;
  }, {});

  const securityCount = prsData.filter(pr =>
    SECURITY_CLASSIFICATIONS.includes(pr.contribution_classification)
  ).length;

  return (
    <section className="contribution-summary">
      <h2>Contribution Summary</h2>
      <div className="summary-grid">
        <div className="summary-card highlight">
          <h3>{securityCount}</h3>
          <p>Security-Related PRs</p>
        </div>
        <div className="summary-card">
          <h3>{classificationCounts['other'] || 0}</h3>
          <p>Other Contributions</p>
        </div>
      </div>

      <div className="classification-breakdown">
        <h3>Breakdown by Classification</h3>
        <ul>
          {Object.entries(classificationCounts)
            .sort(([, a], [, b]) => b - a)
            .map(([classification, count]) => (
              <li key={classification}>
                <span className="classification-name">{classification}</span>
                <span className="classification-count">{count}</span>
              </li>
            ))}
        </ul>
      </div>
    </section>
  );
}

export default ContributionSummary;
