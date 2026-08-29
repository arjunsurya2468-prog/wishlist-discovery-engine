import React from 'react';
import { Star, CheckCircle2, ThumbsUp, ThumbsDown, MoreVertical } from 'lucide-react';

export default function ReviewCardVertical({ rating, date, text, size, concerns, author, helpfulCount }) {
  return (
    <div className="vertical-review-card">
      <div className="v-review-header">
        <div style={{display: 'flex', alignItems: 'center'}}>
          <div className="v-review-rating-chip">
            <span>{rating}</span>
            <Star size={10} fill="white" color="white" />
          </div>
          <span className="v-review-date">{date}</span>
        </div>
      </div>
      
      <div className="v-review-body">
        {text}
      </div>

      <div className="v-review-tags-row">
        <div className="v-size-chip">Size bought: {size}</div>
        {concerns && concerns.map(c => (
          <div key={c} className="v-concern-tag">{c}</div>
        ))}
      </div>

      <div className="v-review-footer">
        <div className="v-reviewer">
          <CheckCircle2 size={14} color="#03a685" />
          <span>{author}</span>
        </div>
        <div className="v-helpful-actions">
          <button className="v-helpful-btn">
            <ThumbsUp size={16} /> {helpfulCount || 0}
          </button>
          <button className="v-helpful-btn">
            <ThumbsDown size={16} />
          </button>
          <button className="v-helpful-btn" style={{marginLeft: '8px'}}>
            <MoreVertical size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
