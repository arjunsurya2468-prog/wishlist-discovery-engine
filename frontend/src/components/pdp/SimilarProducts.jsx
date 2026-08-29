import React from 'react';
import { Star } from 'lucide-react';

export default function SimilarProducts() {
  const products = [
    { brand: 'Imsa Moda', desc: 'Men Henley Neck T-shirt', current: 441, original: 1999, discount: '78% OFF', rating: '4.2', ad: true },
    { brand: 'Black Pigeon', desc: 'Men Printed T-shirt', current: 304, original: 699, discount: '57% OFF' },
    { brand: 'Black Pigeon', desc: 'Men Printed T-shirt', current: 304, original: 699, discount: '57% OFF' },
  ];

  return (
    <div className="pdp-section pdp-carousel-section">
      <div className="section-heading">Similar Products</div>
      
      <div className="carousel-container">
        {products.map((p, i) => (
          <div key={i} className="carousel-card">
            <div className="carousel-image">
              <div className="carousel-placeholder"></div>
              {p.ad && <div className="ad-tag">AD</div>}
              {p.rating && (
                <div className="rating-chip">
                  <span>{p.rating}</span>
                  <Star size={10} fill="#03a685" color="#03a685" />
                </div>
              )}
            </div>
            <div className="carousel-info">
              <div className="carousel-brand">{p.brand}</div>
              <div className="carousel-desc">{p.desc}</div>
              <div className="pdp-price-row small">
                <span className="pdp-strikethrough">₹{p.original}</span>
                <span className="pdp-current-price">₹{p.current}</span>
                <span className="pdp-discount-tag">{p.discount}</span>
              </div>
              <button className="carousel-add-btn">Add to Bag</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
