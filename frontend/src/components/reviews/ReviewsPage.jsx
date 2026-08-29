import React, { useState } from 'react';
import { ArrowLeft, Star, ChevronDown } from 'lucide-react';
import ReviewCardVertical from './ReviewCardVertical';
import '../../reviews.css';

export default function ReviewsPage({ activeConcern, setActiveConcern, onBack }) {
  const [selectedStar, setSelectedStar] = useState('All');

  const starFilters = ['All', '5★', '4★', '3★', '2★', '1★'];
  
  // 4 Fit, 3 Quality, 2 Both = 7 Total
  const reviews = [
    { id: 1, rating: 5, date: 'Apr 14, 2026', text: "It's best product and also under budget 👌 👏 😀 and I am very satisfying after buy this product", author: 'Ayush Morya', size: 'L', concerns: ['Fit', 'Quality'], helpfulCount: 12 },
    { id: 2, rating: 5, date: 'Jun 21, 2026', text: "Worth vermarking product for this humid weather...", author: 'Sohan', size: 'M', concerns: ['Fit'], helpfulCount: 8 },
    { id: 3, rating: 4, date: 'Mar 12, 2026', text: "Good material but sleeves are a bit long.", author: 'Rahul', size: 'XL', concerns: ['Fit', 'Quality'], helpfulCount: 4 },
    { id: 4, rating: 4, date: 'Jan 05, 2026', text: "Nice tshirt, color didn't fade after washing.", author: 'Vikas', size: 'L', concerns: ['Quality'], helpfulCount: 2 },
    { id: 5, rating: 3, date: 'Feb 18, 2026', text: "Average product, fit is slightly tighter than expected.", author: 'Amit', size: 'S', concerns: ['Fit'], helpfulCount: 0 },
    { id: 6, rating: 2, date: 'May 30, 2026', text: "Stitching came off after one wash.", author: 'Deepak', size: 'XXL', concerns: ['Quality'], helpfulCount: 1 },
    { id: 7, rating: 4, date: 'Aug 10, 2026', text: "Overall satisfied, looks exactly like the picture.", author: 'Karan', size: 'M', concerns: [], helpfulCount: 0 },
  ];

  const filteredReviews = reviews.filter(r => {
    // Star filter
    if (selectedStar !== 'All' && r.rating.toString() + '★' !== selectedStar) return false;
    
    // Concern filter
    if (activeConcern !== 'All' && !r.concerns.includes(activeConcern)) return false;

    return true;
  });

  return (
    <div className="reviews-page">
      <div className="pdp-header">
        <button className="icon-button" onClick={onBack}><ArrowLeft size={28} /></button>
        <div className="header-title-group" style={{marginLeft: 0}}>
          <div className="header-title">Ratings & Reviews</div>
        </div>
      </div>

      <div className="reviews-summary-section">
        <div className="rating-top-block">
          <div className="rating-big-score">
            <div className="rating-big-score-value">
              4.1 <Star size={32} fill="#03a685" color="#03a685" />
            </div>
            <div className="rating-big-score-label">31 Ratings & 7 Reviews</div>
          </div>
          
          <div className="rating-distribution">
            {[5, 4, 3, 2, 1].map(stars => (
              <div key={stars} className="dist-row">
                <span>{stars} <Star size={10} fill="#7e818c" color="#7e818c" /></span>
                <div className="dist-bar-bg">
                  <div className="dist-bar-fill" style={{width: stars === 5 ? '60%' : stars === 4 ? '25%' : stars === 3 ? '10%' : '5%'}}></div>
                </div>
                <span>{stars === 5 ? 18 : stars === 4 ? 8 : stars === 3 ? 3 : 1}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="filter-row-container">
        <div className="filter-heading">Filter photos and reviews by</div>
        <div className="filter-scroll-row">
          {starFilters.map(sf => (
            <button 
              key={sf} 
              className={`filter-chip ${selectedStar === sf ? 'selected' : ''}`}
              onClick={() => setSelectedStar(sf)}
            >
              {sf}
            </button>
          ))}
          <div className="filter-divider"></div>
          
          <button 
            className={`filter-chip ${activeConcern === 'Fit' ? 'selected' : ''}`}
            onClick={() => setActiveConcern(activeConcern === 'Fit' ? 'All' : 'Fit')}
          >
            Fit · 4
          </button>
          <button 
            className={`filter-chip ${activeConcern === 'Quality' ? 'selected' : ''}`}
            onClick={() => setActiveConcern(activeConcern === 'Quality' ? 'All' : 'Quality')}
          >
            Quality · 3
          </button>
        </div>
      </div>

      {activeConcern === 'Fit' && (
        <div className="personalisation-line">
          Showing fit reviews — based on items you've returned before. 
          <button onClick={() => setActiveConcern('All')}>Show all</button>
        </div>
      )}

      <div className="reviews-list-container">
        <div className="reviews-list-header">
          <div className="reviews-count">Customer Reviews ({filteredReviews.length})</div>
          <div className="sort-control">
            Most Helpful <ChevronDown size={16} />
          </div>
        </div>

        {filteredReviews.length > 0 ? (
          <div>
            {filteredReviews.map(r => (
              <ReviewCardVertical key={r.id} {...r} />
            ))}
          </div>
        ) : (
          <div className="reviews-empty-state">
            <p>No reviews match your selected filters.</p>
            <button onClick={() => {
              setSelectedStar('All');
              setActiveConcern('All');
            }}>
              Clear Filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
