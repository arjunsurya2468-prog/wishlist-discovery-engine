import React from 'react';
import { ShieldCheck, Award } from 'lucide-react';

export default function TrustBadges() {
  return (
    <div className="pdp-section trust-section">
      <div className="trust-badges-row">
        <div className="trust-badge">
          <div className="badge-icon-wrapper red-badge">
            <Award size={32} />
            <div className="badge-ribbon">ORIGINAL</div>
          </div>
          <div className="trust-badge-label">Genuine<br/>Product</div>
        </div>
        <div className="trust-badge">
          <div className="badge-icon-wrapper blue-badge">
            <ShieldCheck size={32} />
            <div className="badge-ribbon" style={{backgroundColor: '#ff3f6c'}}></div>
          </div>
          <div className="trust-badge-label">Quality<br/>Checked</div>
        </div>
      </div>
      
      <div className="returns-info">
        <div className="returns-title">Easy 7 days returns and exchanges</div>
        <div className="returns-desc">Choose to return or exchange for a different size (if available) within 7 days.</div>
      </div>
    </div>
  );
}
