import React from 'react';
import { ShoppingBag } from 'lucide-react';

export default function PromoBanner({ type }) {
  const isLowStock = type === 'low-stock';
  
  return (
    <div className="promo-banner-wrapper">
      <div className="promo-banner">
        <div className="promo-left">
          <div className="promo-illustration" style={isLowStock ? {} : {backgroundColor: 'rgba(56, 161, 105, 0.2)', color: '#38a169'}}>
            <ShoppingBag size={36} />
          </div>
          <div className="promo-text">
            <div className="promo-title">Stay Updated On</div>
            <div className="promo-subtitle">{isLowStock ? 'Low Stocks!' : 'Price Drops!'}</div>
          </div>
        </div>
        <div className="promo-right">
          <div className="toggle-switch">
            <div className="toggle-knob"></div>
          </div>
          <div className="toggle-label">Allow</div>
        </div>
      </div>
    </div>
  );
}
