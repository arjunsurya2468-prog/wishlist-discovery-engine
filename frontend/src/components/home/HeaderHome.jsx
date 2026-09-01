import React from 'react';
import { Search, Heart, ShoppingBag, Menu } from 'lucide-react';

export default function HeaderHome({ staleItemsCount, onWishlistClick }) {
  return (
    <div className="home-header">
      <div className="home-brand-group">
        <button className="icon-button"><Menu size={24} /></button>
        <div className="home-logo">Myntra</div>
      </div>
      
      <div className="home-search-bar">
        <Search size={18} color="#999" style={{marginRight: '8px'}} />
        <input type="text" placeholder="Search for products, brands and more" className="home-search-input" readOnly />
      </div>

      <div className="home-header-actions">
        <div className="header-icon-container">
          <button className="icon-button" onClick={onWishlistClick}>
            <Heart size={24} />
          </button>
          {staleItemsCount > 0 && <div className="badge">{staleItemsCount}</div>}
        </div>
        <div className="header-icon-container">
          <button className="icon-button"><ShoppingBag size={24} /></button>
          <div className="badge">2</div>
        </div>
      </div>
    </div>
  );
}
