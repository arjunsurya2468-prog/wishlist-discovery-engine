import React from 'react';
import { Layers, PackageX } from 'lucide-react';

export default function ActionPills({ matchCount, onCompareClick, onCollectionClick, isCollection }) {
  return (
    <div className="action-pills-container">
      {matchCount > 0 && (
        <button 
          className="action-pill compare-pill-accent" 
          onClick={onCompareClick}
        >
          Better Matches
          <span className="compare-badge">{matchCount}</span>
        </button>
      )}
      {!isCollection && (
        <button className="action-pill" onClick={onCollectionClick}>
          <Layers size={22} />
          Collections
        </button>
      )}
      <button className="action-pill">
        <PackageX size={22} />
        Out of Stock
      </button>
    </div>
  );
}
