import React from 'react';

export default function MoreInfo({ product }) {
  return (
    <div className="pdp-section">
      <div className="section-heading">More Information</div>
      <div className="more-info-text">Product Code: {product?.productCode || '44164231'}</div>
      <button className="link-button" style={{color: '#ff3f6c', fontWeight: 'bold'}}>View More</button>
    </div>
  );
}
