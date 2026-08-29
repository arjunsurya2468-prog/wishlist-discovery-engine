import React from 'react';

export default function DetailsSection() {
  return (
    <div className="pdp-section">
      <div className="contact-card">
        <div className="contact-heading">Contact Brand or Retailer for pre-sales product queries</div>
        <div className="contact-email">info@kartbin.com</div>
        
        <div className="specs-grid">
          <div className="spec-item">
            <div className="spec-label">Fit</div>
            <div className="spec-value">Regular Fit</div>
          </div>
          <div className="spec-item">
            <div className="spec-label">Sustainable</div>
            <div className="spec-value">Regular</div>
          </div>
          <div className="spec-item">
            <div className="spec-label">Closure</div>
            <div className="spec-value">Button</div>
          </div>
          <div className="spec-item">
            <div className="spec-label">Fabrics</div>
            <div className="spec-value">Cotton</div>
          </div>
        </div>

        <div className="details-block">
          <div className="details-heading">Product Details</div>
          <ul className="details-list">
            <li>Black Tshirt for Men</li>
            <li>Solid</li>
            <li>Regular length</li>
            <li>Henley Neck</li>
            <li>Long, Regular Sleeves</li>
            <li>Knitted Cotton fabric</li>
            <li>Button closure</li>
          </ul>
        </div>

        <div className="details-block">
          <div className="details-heading">Size & Fit</div>
          <div className="details-text">
            Regular Fit<br/>
            The model (height 6') is wearing a size M
          </div>
        </div>

        <div className="details-block">
          <div className="details-heading">Material & Care</div>
          <div className="details-text">Machine wash.Do not bleach.Warm iron inside out</div>
        </div>

        <div className="details-block" style={{border: '1px solid #eaeaec', padding: '16px', borderRadius: '12px'}}>
          <div className="details-heading" style={{marginTop: 0}}>Style Note</div>
          <div className="details-text">
            Pair This Henley T-Shirt With Denim Or Chinos And Sneakers Or Boots For A Smart Casual Look. Perfect For Layering Under Jackets Or Wearing Solo Across Seasons.
          </div>
        </div>
      </div>
    </div>
  );
}
