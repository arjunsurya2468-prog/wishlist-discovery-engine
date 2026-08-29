import React from 'react';
import { Star, Heart } from 'lucide-react';

export default function Recommendations() {
  const products = [
    { brand: 'RAE ZONE', desc: 'Men Printed T-shirt', current: 444, original: 999, discount: '56% OFF', delivery: 'Delivery by 30 Aug' },
    { brand: 'London Hills', desc: 'Men Full Sleeve T-Shirt', current: 393, original: 1299, discount: '70% OFF', rating: '4.1' },
    { brand: 'DAMENSCH', desc: 'Pack Of 3 Deo-Cotton Tr...', current: 879, original: 1045, discount: '16% OFF', rating: '4.5', image: '3-PACK' },
    { brand: 'U.S. Polo Assn.', desc: 'Men Pure Cotton Lounge...', current: 902, original: 949, discount: '5% OFF', rating: '4.4' }
  ];

  return (
    <div className="pdp-section pdp-recommendations">
      <div className="section-heading">Products you may like</div>
      
      <div className="tabs-row">
        <div className="pill-tab selected">All</div>
        <div className="pill-tab">Similar</div>
        <div className="pill-tab">Your Next Favourites</div>
      </div>

      <div className="pdp-product-grid">
        {products.map((p, i) => (
          <div key={i} className="pdp-grid-card">
            <div className="pdp-grid-image">
               <div className="carousel-placeholder"></div>
               <button className="heart-top-right"><Heart size={18} /></button>
               {p.rating && (
                <div className="rating-chip bottom-left">
                  <span>{p.rating}</span>
                  <Star size={10} fill="#03a685" color="#03a685" />
                </div>
              )}
            </div>
            <div className="pdp-grid-info">
              <div className="carousel-brand">{p.brand}</div>
              <div className="carousel-desc">{p.desc}</div>
              <div className="pdp-price-row small">
                <span className="pdp-strikethrough">₹{p.original}</span>
                <span className="pdp-current-price">₹{p.current}</span>
                <span className="pdp-discount-tag">{p.discount}</span>
              </div>
              {p.delivery && <div className="pdp-delivery-subtext">{p.delivery}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
