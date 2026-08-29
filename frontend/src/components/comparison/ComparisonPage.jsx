import React from 'react';
import { ArrowLeft } from 'lucide-react';
import ComparisonRow from './ComparisonRow';
import '../../comparison.css';

export default function ComparisonPage({ comparisons, onDismissItem, onBack }) {
  return (
    <div className="comparison-page">
      <div className="pdp-header" style={{ borderBottom: 'none' }}>
        <button className="icon-button" onClick={onBack}>
          <ArrowLeft size={28} />
        </button>
        <div className="header-title-group" style={{ marginLeft: 0 }}>
          <div className="header-title">Better Matches</div>
        </div>
      </div>
      
      {comparisons.length > 0 && (
        <div className="comparison-header-context">
          Compared on fit — based on items you've returned before.
        </div>
      )}

      <div className="comparison-list">
        {comparisons.length > 0 ? (
          comparisons.map(item => (
            <ComparisonRow 
              key={item.id} 
              item={item} 
              onDismiss={() => onDismissItem(item.id)} 
            />
          ))
        ) : (
          <div className="comparison-empty">
            <div className="comparison-empty-title">All caught up!</div>
            <p>You've reviewed all your better fit matches.</p>
            <button onClick={onBack}>Back to Wishlist</button>
          </div>
        )}
      </div>
    </div>
  );
}
