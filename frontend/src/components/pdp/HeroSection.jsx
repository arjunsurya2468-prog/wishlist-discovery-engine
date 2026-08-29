import React from 'react';
import { Share2, Heart, RefreshCcw, Star, ChevronRight, ShoppingBag } from 'lucide-react';

export default function HeroSection() {
  return (
    <div className="pdp-section">
      <div className="hero-image-container">
        <div className="hero-placeholder"></div>
        <div className="hero-rating-badge">
          <span style={{ fontWeight: 'bold' }}>4.1</span>
          <Star size={12} fill="#03a685" color="#03a685" />
          <div className="vertical-divider"></div>
          <span>31</span>
        </div>
      </div>
      
      <div className="hero-pagination">
        <div className="dot dot-active"></div>
        <div className="dot"></div>
        <div className="dot"></div>
        <div className="dot"></div>
      </div>

      <div className="pdp-action-row">
        <button className="pdp-action-pill"><RefreshCcw size={16} /> Compare</button>
        <button className="pdp-action-pill"><Heart size={16} /> Wishlist</button>
        <button className="pdp-action-pill"><Share2 size={16} /> Share</button>
      </div>

      <div className="pdp-title-block">
        <div className="pdp-brand-title">London Hills</div>
        <div className="pdp-product-name">Men Henley Neck T-shirt</div>
        <div className="pdp-price-row">
          <span className="pdp-mrp-label">MRP</span>
          <span className="pdp-strikethrough">₹1,299</span>
          <span className="pdp-current-price">₹393</span>
          <span className="pdp-discount-tag">70% OFF!</span>
        </div>
      </div>

      <div className="mega-deal-banner">
        <div className="mega-deal-left">
          <div className="mega-deal-icon">MEGA DEAL</div>
          <div className="mega-deal-text">Get at <span className="mega-deal-price">₹364</span></div>
        </div>
        <button className="mega-deal-btn">Extra ₹29 Off</button>
      </div>

      <div className="bank-offer-row">
        <div className="bank-offer-left">
          <div className="bank-icon-placeholder"></div>
          <span>With Bank Offer</span>
        </div>
        <button className="red-link">Details <ChevronRight size={16} /></button>
      </div>

      <div className="color-selector">
        <div className="selector-title"><strong>Colour</strong> Black</div>
        <div className="color-thumbnails">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className={`color-thumb ${i === 6 ? 'selected' : ''}`}></div>
          ))}
        </div>
      </div>

      <div className="size-selector">
        <div className="size-header">
          <div className="selector-title"><strong>Size: L</strong></div>
          <button className="red-link">Size Chart <ChevronRight size={16} /></button>
        </div>
        <div className="size-subtext">GARMENT: Chest 42.0in</div>
        <div className="size-pills">
          {['S', 'M', 'L', 'XL', 'XXL'].map(size => (
            <div key={size} className={`size-pill ${size === 'L' ? 'selected' : ''}`}>{size}</div>
          ))}
        </div>
      </div>

      <div className="sticky-bottom-actions">
        <button className="pdp-btn-outline"><ShoppingBag size={20}/> Buy Now</button>
        <button className="pdp-btn-filled"><ShoppingBag size={20}/> Add to Bag</button>
      </div>
    </div>
  );
}
