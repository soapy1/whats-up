import React, { useState } from 'react';

function extractPackageName(repository) {
  const repoName = repository.split('/').pop();
  return repoName.endsWith('-feedstock') ? repoName.slice(0, -'-feedstock'.length) : repoName;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function PackageModal({ pkg, prs, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{pkg} — Security Fixes</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Date</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {prs.map((pr) => (
                <tr key={pr.url}>
                  <td>
                    <a href={pr.url} target="_blank" rel="noopener noreferrer">
                      {pr.title}
                    </a>
                  </td>
                  <td>{formatDate(pr.created_at)}</td>
                  <td>
                    <span className={`state-badge state-${pr.state}`}>{pr.state}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function TopSecurityPackages({ prsData }) {
  const [selectedPkg, setSelectedPkg] = useState(null);

  const securityPRs = prsData.filter(pr => pr.contribution_classification === 'security');

  const prsByPackage = securityPRs.reduce((acc, pr) => {
    const pkg = extractPackageName(pr.repository);
    if (!acc[pkg]) acc[pkg] = [];
    acc[pkg].push(pr);
    return acc;
  }, {});

  const topPackages = Object.entries(prsByPackage)
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 5);

  const selectedPRs = selectedPkg ? (prsByPackage[selectedPkg] || []) : [];

  return (
    <section className="top-security-packages">
      <h2>Top Packages by Security Fixes</h2>
      <div className="table-responsive">
        <table>
          <thead>
            <tr>
              <th>Package</th>
              <th>Security Issues Fixed</th>
            </tr>
          </thead>
          <tbody>
            {topPackages.length === 0 ? (
              <tr>
                <td colSpan="2">No security contributions in this date range</td>
              </tr>
            ) : (
              topPackages.map(([pkg, prs]) => (
                <tr key={pkg} className="clickable-row" onClick={() => setSelectedPkg(pkg)}>
                  <td>{pkg}</td>
                  <td>{prs.length}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedPkg && (
        <PackageModal
          pkg={selectedPkg}
          prs={selectedPRs}
          onClose={() => setSelectedPkg(null)}
        />
      )}
    </section>
  );
}

export default TopSecurityPackages;
