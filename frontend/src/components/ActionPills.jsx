import React from 'react';
import { Layers, PackageX } from 'lucide-react';

export default function ActionPills({ matchCount, onCompareClick }) {
  return (
    <div className="action-pills-container">
      <button className="action-pill">
        <Layers size={22} />
        Collections
      </button>
      <button className="action-pill">
        <PackageX size={22} />
        Out of Stock
      </button>
      {matchCount > 0 && (
        <button 
          className="action-pill compare-pill-accent" 
          onClick={onCompareClick}
        >
          Better matches · {matchCount}
        </button>
      )}
    </div>
  );
}
