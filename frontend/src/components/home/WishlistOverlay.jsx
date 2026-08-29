import React from 'react';
import { X } from 'lucide-react';
import '../../home.css';

export default function WishlistOverlay({ onDismiss, onViewItem, onSeeAlternatives }) {
  const stopPropagation = (e) => {
    e.stopPropagation();
  };

  return (
    <div className="wishlist-overlay-scrim" onClick={onDismiss}>
      <div className="wishlist-overlay-card" onClick={(e) => { stopPropagation(e); onViewItem(); }}>
        <button className="overlay-dismiss" onClick={(e) => { stopPropagation(e); onDismiss(); }} aria-label="Dismiss">
          <X size={20} />
        </button>

        {/* 1. Saved Product Image (LARGE and dominant) */}
        <img src="/grey_sweatshirt.jpg" alt="Grey Sweatshirt" className="overlay-image" />

        <div className="overlay-content">
          {/* Headline */}
          <div className="overlay-headline">Still saved for you</div>

          {/* Time context */}
          <div className="overlay-time">
            You added this on 4 August
          </div>

          {/* Product name for identification only */}
          <div className="overlay-name">Roadster · Men Grey Solid Sweatshirt</div>

          {/* Availability - plain treatment */}
          <div className="overlay-availability">Still available in L</div>

          {/* Actions & Alternatives */}
          <div className="overlay-footer">
            <button className="overlay-secondary-line interactive" onClick={(e) => { stopPropagation(e); onSeeAlternatives(); }}>
              See picks with better fit reviews
            </button>
            
            <button className="overlay-primary-btn" onClick={(e) => { stopPropagation(e); onViewItem(); }}>
              View item
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
