import React, { useState } from 'react';
import { ArrowLeft, Star, ChevronDown } from 'lucide-react';
import ReviewCardVertical from './ReviewCardVertical';
import '../../reviews.css';
import { REVIEW_STATS } from '../../reviewStats.js';

export default function ReviewsPage({ activeConcern, setActiveConcern, onBack }) {
  const [selectedStar, setSelectedStar] = useState('All');

  const starFilters = ['All', '5★', '4★', '3★', '2★', '1★'];
  
  // Representative review cards; the counters reflect the full review set.
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

  const displayedReviewCount = selectedStar === 'All'
    ? activeConcern === 'Fit'
      ? REVIEW_STATS.fitReviewsCount
      : activeConcern === 'Quality'
        ? REVIEW_STATS.qualityReviewsCount
        : REVIEW_STATS.reviewsCount
    : filteredReviews.length;

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
            <div className="rating-big-score-label">
              {REVIEW_STATS.ratingsCount} Ratings & {REVIEW_STATS.reviewsCount} Reviews
            </div>
          </div>
          
          <div className="rating-distribution">
            {[5, 4, 3, 2, 1].map(stars => (
              <div key={stars} className="dist-row">
                <span>{stars} <Star size={10} fill="#7e818c" color="#7e818c" /></span>
                <div className="dist-bar-bg">
                  <div className="dist-bar-fill" style={{width: stars === 5 ? '60%' : stars === 4 ? '25%' : stars === 3 ? '10%' : '5%'}}></div>
                </div>
                <span>{stars === 5 ? 139 : stars === 4 ? 58 : stars === 3 ? 23 : stars === 2 ? 7 : 4}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="filter-row-container">
        <div className="filter-heading">Filter photos and reviews by</div>

        {/* Rating Row */}
        <div className="filter-scroll-row" style={{marginBottom: '12px'}}>
          <div className="filter-row-label">Rating:</div>
          {starFilters.map(sf => (
            <button 
              key={sf} 
              className={`filter-chip ${selectedStar === sf ? 'selected' : ''}`}
              onClick={() => setSelectedStar(sf)}
            >
              {sf}
            </button>
          ))}
        </div>

        {/* Shows Row */}
        <div className="filter-scroll-row">
          <div className="filter-row-label">Shows:</div>
          <button 
            className={`filter-chip ${activeConcern === 'Fit' ? 'selected' : ''}`}
            onClick={() => setActiveConcern(activeConcern === 'Fit' ? 'All' : 'Fit')}
          >
            Fit · {REVIEW_STATS.fitReviewsCount}
          </button>
          <button 
            className={`filter-chip ${activeConcern === 'Quality' ? 'selected' : ''}`}
            onClick={() => setActiveConcern(activeConcern === 'Quality' ? 'All' : 'Quality')}
          >
            Quality · {REVIEW_STATS.qualityReviewsCount}
          </button>
        </div>
      </div>

      {activeConcern === 'Fit' && (
        <div className="personalisation-line">
          Showing fit reviews — based on items you've returned before. 
          <button onClick={() => setActiveConcern('All')}>Show all reviews</button>
        </div>
      )}

      <div className="reviews-list-container">
        <div className="reviews-list-header">
          <div className="reviews-count">Customer Reviews ({displayedReviewCount})</div>
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
