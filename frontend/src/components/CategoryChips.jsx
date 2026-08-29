import React from 'react';

export default function CategoryChips({ chips }) {
  return (
    <div className="category-chips-container">
      {chips.map((chip, i) => (
        <div key={i} className="category-chip">
          <div className="chip-circle">
             <div className="chip-placeholder"></div>
          </div>
          <div className="chip-label">{chip.label}</div>
        </div>
      ))}
    </div>
  );
}
