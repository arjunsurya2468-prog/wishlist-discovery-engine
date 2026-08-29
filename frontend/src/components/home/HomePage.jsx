import React from 'react';
import HeaderHome from './HeaderHome';
import '../../home.css';

export default function HomePage({ staleItemsCount, onWishlistClick }) {
  return (
    <div className="home-feed-page">
      <HeaderHome staleItemsCount={staleItemsCount} onWishlistClick={onWishlistClick} />
      
      <div className="scrollable-content" style={{ backgroundColor: '#f5f5f5' }}>
        
        {/* Promotional Banner */}
        <div className="promo-carousel-dummy">
          <div className="promo-carousel-content">
            <span className="promo-carousel-text">Up To 50% Off<br/><b>H&M | MANGO</b></span>
          </div>
        </div>

        {/* Cashback Strip */}
        <div className="cashback-strip-dummy">
          <div className="cashback-icon"></div>
          <div>
            <div style={{fontWeight: 800, fontSize: '13px', color: '#1a202c'}}>Get 7.5% Cashback*</div>
            <div style={{fontSize: '10px', color: '#718096'}}>With FLIPKART AXIS BANK Credit Card</div>
          </div>
          <button className="cashback-btn">Apply Now &gt;</button>
        </div>

        {/* Featured Brands */}
        <div className="featured-brands-header">
          <h2>Continue Browsing These Brands</h2>
        </div>
        
        <div className="brand-cards-row">
          <div className="brand-card-dummy">
            <div className="brand-card-image bg-1"></div>
            <div className="brand-card-footer">
              <div className="brand-card-title">LONDON HILLS</div>
              <div className="brand-card-sub">TSHIRTS</div>
            </div>
          </div>
          <div className="brand-card-dummy">
            <div className="brand-card-image bg-2"></div>
            <div className="brand-card-footer">
              <div className="brand-card-title">AZZARO</div>
              <div className="brand-card-sub">PERFUME</div>
            </div>
          </div>
        </div>

        <div className="featured-brands-header">
          <h2>Top Stories Of The Week</h2>
          <span style={{fontSize: '13px', color: '#718096', marginTop: '4px'}}>In the spotlight</span>
        </div>

        <div className="promo-carousel-dummy tall">
          <div className="promo-carousel-content">
            <span className="promo-carousel-text">TRENDING NOW</span>
          </div>
        </div>

        <div style={{height: '24px'}}></div>
      </div>
    </div>
  );
}
