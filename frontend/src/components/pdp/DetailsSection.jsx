import React from 'react';

const CATEGORY_DETAILS = {
  tshirt: {
    closure: 'Button',
    fabric: 'Cotton',
    items: ['Black Tshirt for Men', 'Solid', 'Regular length', 'Henley Neck', 'Long, Regular Sleeves', 'Knitted Cotton fabric', 'Button closure'],
    styleNote: 'Pair This Henley T-Shirt With Denim Or Chinos And Sneakers Or Boots For A Smart Casual Look. Perfect For Layering Under Jackets Or Wearing Solo Across Seasons.',
  },
  sweatshirt: {
    closure: 'Pullover',
    fabric: 'Cotton Blend',
    items: ['Grey sweatshirt for Men', 'Solid', 'Regular length', 'Round Neck', 'Long sleeves', 'Knitted cotton-blend fabric', 'Pullover closure'],
    styleNote: 'Layer this grey sweatshirt over a T-shirt and pair it with denim or joggers for an easy everyday look.',
  },
};

export default function DetailsSection({ product }) {
  const details = CATEGORY_DETAILS[product?.category] || CATEGORY_DETAILS.tshirt;

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
            <div className="spec-value">{details.closure}</div>
          </div>
          <div className="spec-item">
            <div className="spec-label">Fabrics</div>
            <div className="spec-value">{details.fabric}</div>
          </div>
        </div>

        <div className="details-block">
          <div className="details-heading">Product Details</div>
          <ul className="details-list">
            {details.items.map((item) => <li key={item}>{item}</li>)}
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
            {details.styleNote}
          </div>
        </div>
      </div>
    </div>
  );
}
