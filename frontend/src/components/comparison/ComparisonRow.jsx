import React, { useState } from 'react';
import { X, Heart, RefreshCw, Undo2 } from 'lucide-react';

export default function ComparisonRow({ item, onDismiss }) {
  const [isReplaced, setIsReplaced] = useState(false);

  return (
    <div className="comparison-row">
      <button className="comparison-row-dismiss" onClick={onDismiss} aria-label="Dismiss">
        <X size={20} />
      </button>

      <div className="comparison-cards-wrapper">
        <div className="vs-badge">VS</div>
        
        {/* LEFT CARD (Saved Item) */}
        <div className="compare-card">
          <div className="qualifier-placeholder"></div>
          <div className="compare-image"></div>
          <div className="compare-brand">{item.saved.brand}</div>
          <div className="compare-name">{item.saved.name}</div>
          
          <div className="evidence-block">
            <span className="evidence-text">{item.saved.reviews} fit reviews</span>
            <span className="evidence-bold warning">{item.saved.score} on fit</span>
            <div className="evidence-scale-bar-track">
              <div 
                className="evidence-scale-bar-fill warning" 
                style={{ width: `${(parseFloat(item.saved.score) / 5) * 100}%` }}
              ></div>
            </div>
          </div>

          <div className="compare-price-row">
            <span className="compare-current">₹{item.saved.price}</span>
          </div>
        </div>

        {/* RIGHT CARD (Alternative) */}
        <div className="compare-card">
          <div className="qualifier-tag">Better reviewed for fit</div>
          <div className="compare-image"></div>
          <div className="compare-brand">{item.alt.brand}</div>
          <div className="compare-name">{item.alt.name}</div>
          
          <div className="evidence-block">
            <span className="evidence-text">{item.alt.reviews} fit reviews</span>
            <span className="evidence-bold good">{item.alt.score} on fit</span>
            <div className="evidence-scale-bar-track">
              <div 
                className="evidence-scale-bar-fill good" 
                style={{ width: `${(parseFloat(item.alt.score) / 5) * 100}%` }}
              ></div>
            </div>
          </div>

          <div className="compare-price-row">
            <span className="compare-current">₹{item.alt.price}</span>
            {item.alt.mrp && <span className="compare-mrp">₹{item.alt.mrp}</span>}
          </div>
          <div className="price-diff-line">
            {item.alt.price > item.saved.price 
              ? `₹${item.alt.price - item.saved.price} more` 
              : item.alt.price < item.saved.price 
                ? `₹${item.saved.price - item.alt.price} less` 
                : 'Same price'}
          </div>
        </div>
      </div>

      {/* ACTIONS */}
      <div className="compare-actions-wrapper">
        <div className="compare-actions-split">
          <div className="action-col-left">
            <button className="keep-this-link" onClick={onDismiss}>Keep this one</button>
          </div>
          <div className="action-col-right">
            <button className="compare-primary-btn">Add to Bag</button>
          </div>
        </div>
        
        <div className="compare-secondary-row">
          {!isReplaced ? (
            <button className="compare-secondary-btn" onClick={() => setIsReplaced(true)}>
              <RefreshCw size={16} style={{marginRight: '6px'}} /> Replace in wishlist
            </button>
          ) : (
            <button className="compare-secondary-btn undo-state" onClick={() => setIsReplaced(false)}>
              <Undo2 size={16} style={{marginRight: '6px'}} /> Undo replacement
            </button>
          )}
          <button className="compare-icon-btn">
            <Heart size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
