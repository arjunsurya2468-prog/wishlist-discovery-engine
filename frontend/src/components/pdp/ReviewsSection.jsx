import React from 'react';
import { Star, ChevronRight, CheckCircle2 } from 'lucide-react';
import { REVIEW_STATS } from '../../reviewStats.js';

export default function ReviewsSection({ activeConcern, setActiveConcern, onViewAll, product }) {
  const rating = product?.rating || '4.1';
  const ratingsCount = product?.ratingsCount ?? REVIEW_STATS.ratingsCount;
  const reviewsCount = product?.reviewsCount ?? REVIEW_STATS.reviewsCount;
  const fitReviewsCount = product?.fitReviewsCount ?? REVIEW_STATS.fitReviewsCount;
  const qualityReviewsCount = product?.qualityReviewsCount ?? REVIEW_STATS.qualityReviewsCount;

  const reviews = [
    { size: 'L', date: 'Apr 14, 2026', text: "It's best product and also under budget 👌 👏 😀 and I am very satisfying after buy this product", author: 'Ayush Morya', rating: '5' },
    { size: 'M', date: 'Jun 21, 2026', text: "Worth vermarking product for this humid weather...", author: 'Sohan', rating: '5' },
  ];

  return (
    <div className="pdp-section">
      <div className="section-heading">Ratings & Reviews</div>
      
      <div className="ratings-summary-row">
        <div className="rating-badge-large">
          <span>{rating}</span>
          <Star size={16} fill="white" color="white" />
        </div>
        <button className="ratings-count-pill" onClick={onViewAll}>
          {ratingsCount} ratings | {reviewsCount} reviews <ChevronRight size={16} />
        </button>
      </div>

      <div className="filter-scroll-row" style={{marginBottom: '16px'}}>
        {[
          { id: 'All', label: 'All' },
          { id: 'Fit', label: `Fit · ${fitReviewsCount}` },
          { id: 'Quality', label: `Quality · ${qualityReviewsCount}` }
        ].map(concern => (
          <button 
            key={concern.id}
            className={`filter-chip ${activeConcern === concern.id ? 'selected' : ''}`}
            onClick={() => setActiveConcern(concern.id)}
          >
            {concern.label}
          </button>
        ))}
      </div>

      {activeConcern === 'Fit' && (
        <div className="personalisation-line" style={{marginBottom: '24px'}}>
          Showing fit reviews — based on items you've returned before.
          <button onClick={() => setActiveConcern('All')}>Show all reviews</button>
        </div>
      )}

      <div className="reviews-header">
        <div className="section-heading" style={{margin:0}}>Customer Reviews ({reviewsCount})</div>
        <button className="link-button underlined" onClick={onViewAll}>View All</button>
      </div>

      <div className="reviews-carousel">
        {reviews.map((r, i) => (
          <div key={i} className="review-card">
            <div className="review-card-header">
              <div className="review-rating-chip">
                <span>{r.rating}</span>
                <Star size={10} fill="white" color="white" />
              </div>
              <span className="review-date">{r.date}</span>
              <div className="review-size-chip">Size: {r.size}</div>
            </div>
            <div className="review-body">{r.text}</div>
            <div className="review-author">
              <CheckCircle2 size={14} color="#03a685" />
              <span>{r.author}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
