import React, { useState } from 'react';
import { X, Heart, RefreshCw, Undo2 } from 'lucide-react';

export default function ComparisonRow({ item, onDismiss, onViewProduct, onViewReviews }) {
  const [isReplaced, setIsReplaced] = useState(false);

  const priceDiff = item.alt.price - item.saved.price;
  const priceDiffText = priceDiff > 0
    ? `+₹${priceDiff}`
    : priceDiff < 0
      ? `−₹${Math.abs(priceDiff)}`
      : 'Same price';
  const priceDiffClass = priceDiff < 0 ? 'price-diff-savings' : '';

  return (
    <div className="comparison-row">
      <button className="comparison-row-dismiss" onClick={onDismiss} aria-label="Dismiss">
        <X size={20} />
      </button>

      <div className="comparison-cards-wrapper">
        <div className="vs-badge">VS</div>

        {/* LEFT CARD (Saved Item) */}
        <div className="compare-card">
          <img src={item.saved.image} alt={item.saved.name} className="compare-image" onClick={onViewProduct} role="button" tabIndex={0} aria-label="View saved product" />
          <div className="compare-brand">{item.saved.brand}</div>
          <div className="compare-name">{item.saved.name}</div>

          <div className="evidence-block">
            <button className="evidence-review-link" onClick={onViewReviews}>{item.saved.reviews} fit reviews</button>
            <span className="evidence-bold neutral">{item.saved.score} on fit</span>
            <div className="evidence-scale-bar-track">
              <div
                className="evidence-scale-bar-fill neutral"
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
          <img src={item.alt.image} alt={item.alt.name} className="compare-image" onClick={onViewProduct} role="button" tabIndex={0} aria-label="View alternative product" />
          <div className="qualifier-tag">Better reviewed for fit</div>
          <div className="compare-brand">{item.alt.brand}</div>
          <div className="compare-name">{item.alt.name}</div>

          <div className="evidence-block">
            <button className="evidence-review-link" onClick={onViewReviews}>{item.alt.reviews} fit reviews</button>
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
          <div className={`price-diff-line ${priceDiffClass}`}>
            {priceDiffText}
          </div>
        </div>
      </div>

      {/* ACTIONS */}
      <div className="compare-actions-wrapper">
        <div className="compare-actions-split">
          <div className="action-col-left">
            <button className="keep-this-btn" onClick={onDismiss}>Keep this one</button>
          </div>
          <div className="action-col-right">
            <button className="compare-primary-btn">Add to Bag</button>
          </div>
        </div>

        <div className="compare-secondary-row">
          {!isReplaced ? (
            <button className="compare-secondary-btn" onClick={() => setIsReplaced(true)}>
              <RefreshCw size={16} style={{ marginRight: '6px' }} /> Swap for this in wishlist
            </button>
          ) : (
            <button className="compare-secondary-btn undo-state" onClick={() => setIsReplaced(false)}>
              <Undo2 size={16} style={{ marginRight: '6px' }} /> Undo swap
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
