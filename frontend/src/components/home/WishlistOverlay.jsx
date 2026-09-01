import React from 'react';
import { X } from 'lucide-react';
import '../../home.css';
import overlayImg from '../../assets/grey_sweatshirt.jpg';

export default function WishlistOverlay({ onDismiss, onViewItem, product }) {
  const displayProduct = product || {
    brand: 'Roadster',
    name: 'Men Grey Solid Sweatshirt',
    image: overlayImg,
    selectedSize: 'L',
  };

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
        <img src={displayProduct.image} alt={displayProduct.name} className="overlay-image" style={{objectFit: 'cover', objectPosition: 'center'}} />

        <div className="overlay-content">
          {/* Headline */}
          <div className="overlay-headline">You saved this</div>

          {/* Time context */}
          <div className="overlay-time">
            You added this to your wishlist on 4 August
          </div>

          {/* Product name for identification only */}
          <div className="overlay-name">{displayProduct.brand} · {displayProduct.name}</div>

          {/* Availability - plain treatment */}
          <div className="overlay-availability">Still available in {displayProduct.selectedSize}</div>

          {/* Actions */}
          <div className="overlay-footer">
            <button className="overlay-primary-btn" onClick={(e) => { stopPropagation(e); onViewItem(); }}>
              View item
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
