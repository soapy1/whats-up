import React from 'react';

function DateRangeFilter({ startDate, endDate, onStartDateChange, onEndDateChange }) {
  return (
    <section className="date-range-filter">
      <h2>Filter by Time Period</h2>
      <div className="filter-controls">
        <div className="date-input-group">
          <label htmlFor="start-date">From:</label>
          <input
            id="start-date"
            type="date"
            value={startDate || ''}
            onChange={(e) => onStartDateChange(e.target.value)}
          />
        </div>
        <div className="date-input-group">
          <label htmlFor="end-date">To:</label>
          <input
            id="end-date"
            type="date"
            value={endDate || ''}
            onChange={(e) => onEndDateChange(e.target.value)}
          />
        </div>
      </div>
    </section>
  );
}

export default DateRangeFilter;
