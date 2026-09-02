import React from 'react';
import { Share2, Heart, RefreshCcw, Star, ChevronRight, ShoppingBag } from 'lucide-react';
import heroImg from '../../assets/black_tshirt.jpg';
import { REVIEW_STATS } from '../../reviewStats.js';

const DEFAULT_PRODUCT = {
  brand: 'London Hills',
  name: 'Men Henley Neck T-shirt',
  image: heroImg,
  currentPrice: 393,
  originalPrice: 1299,
  discount: '70% OFF!',
  dealPrice: 364,
  extraOff: 29,
  rating: '4.1',
  ratingsCount: REVIEW_STATS.ratingsCount,
  color: 'Black',
  selectedSize: 'L',
  chest: '42.0in',
};

function formatPrice(price) {
  return price.toLocaleString('en-IN');
}

export default function HeroSection({ product = DEFAULT_PRODUCT }) {
  return (
    <div className="pdp-section">
      <div className="hero-image-container">
        <img src={product.image} alt={product.name} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
        <div className="hero-rating-badge">
          <span style={{ fontWeight: 'bold' }}>{product.rating}</span>
          <Star size={12} fill="#03a685" color="#03a685" />
          <div className="vertical-divider"></div>
          <span>{product.ratingsCount}</span>
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
        <div className="pdp-brand-title">{product.brand}</div>
        <div className="pdp-product-name">{product.name}</div>
        <div className="pdp-price-row">
          <span className="pdp-mrp-label">MRP</span>
          <span className="pdp-strikethrough">₹{formatPrice(product.originalPrice)}</span>
          <span className="pdp-current-price">₹{formatPrice(product.currentPrice)}</span>
          <span className="pdp-discount-tag">{product.discount}</span>
        </div>
      </div>

      <div className="mega-deal-banner">
        <div className="mega-deal-left">
          <div className="mega-deal-icon">MEGA DEAL</div>
          <div className="mega-deal-text">Get at <span className="mega-deal-price">₹{formatPrice(product.dealPrice)}</span></div>
        </div>
        <button className="mega-deal-btn">Extra ₹{product.extraOff} Off</button>
      </div>

      <div className="bank-offer-row">
        <div className="bank-offer-left">
          <div className="bank-icon-placeholder"></div>
          <span>With Bank Offer</span>
        </div>
        <button className="red-link">Details <ChevronRight size={16} /></button>
      </div>

      <div className="color-selector">
        <div className="selector-title"><strong>Colour</strong> {product.color}</div>
        <div className="color-thumbnails">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className={`color-thumb ${i === 6 ? 'selected' : ''}`}>
              <img src={product.image} alt="" style={{width: '100%', height: '100%', objectFit: 'cover', borderRadius: '4px'}} />
            </div>
          ))}
        </div>
      </div>

      <div className="size-selector">
        <div className="size-header">
          <div className="selector-title"><strong>Size: {product.selectedSize}</strong></div>
          <button className="red-link">Size Chart <ChevronRight size={16} /></button>
        </div>
        <div className="size-subtext">GARMENT: Chest {product.chest}</div>
        <div className="size-pills">
          {['S', 'M', 'L', 'XL', 'XXL'].map(size => (
            <div key={size} className={`size-pill ${size === product.selectedSize ? 'selected' : ''}`}>{size}</div>
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
