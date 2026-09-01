import React from 'react';
import { ArrowLeft, Search, Heart, ShoppingBag } from 'lucide-react';

export default function HeaderPDP({ staleItemsCount = 0, onBack, onWishlist }) {
  return (
    <div className="pdp-header">
      <button className="icon-button" onClick={onBack} aria-label="Go Back"><ArrowLeft size={28} /></button>
      <div className="pdp-search-bar">
        <div className="pdp-logo-m">M</div>
        <input type="text" placeholder="Search in Myntra" className="pdp-search-input" readOnly />
        <Search size={20} className="pdp-search-icon" color="#999" />
      </div>
      <div className="pdp-header-actions">
        <div className="header-icon-container">
          <button className="icon-button" onClick={onWishlist} aria-label="Go to Wishlist"><Heart size={28} /></button>
          {staleItemsCount > 0 && <div className="badge">{staleItemsCount}</div>}
        </div>
        <div className="header-icon-container">
          <button className="icon-button" aria-label="Cart"><ShoppingBag size={28} /></button>
          <div className="badge">2</div>
        </div>
      </div>
    </div>
  );
}
