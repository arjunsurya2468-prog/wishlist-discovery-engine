import React from 'react';

export default function QuoteBlock() {
  return (
    <div className="quote-block">
      <div className="quote-icon">
        <svg width="40" height="12" viewBox="0 0 40 12" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M2 6C6 10 10 2 14 6C18 10 22 2 26 6C30 10 34 2 38 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className="quote-text">
        "Clothes are like a good meal, a good movie, great pieces of music."
      </div>
      <div className="quote-author">
        Michael Kors
      </div>
    </div>
  );
}
