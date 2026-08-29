import React from 'react';
import { MapPin, CheckCircle2, Package, CreditCard, RefreshCw, ChevronRight } from 'lucide-react';

export default function DeliverySection() {
  return (
    <div className="pdp-section bordered-top">
      <div className="section-heading">Delivery & Services</div>
      
      <div className="delivery-address-card">
        <MapPin size={20} color="#7e818c" />
        <div className="delivery-address-text">
          <strong>Zuari Nagar</strong> - South Goa, Vasco Da Gama,...
        </div>
        <button className="link-button">Change</button>
      </div>

      <div className="delivery-estimate-banner">
        <div className="estimate-left">
          <CheckCircle2 size={20} fill="#ff3f6c" color="white" />
          <div className="estimate-text-block">
            <div className="estimate-label"><Package size={14} /> STANDARD</div>
            <div className="estimate-date">Delivery by Tue, 1 Sep</div>
          </div>
        </div>
        <div className="estimate-right">
          <div className="estimate-mrp">MRP ₹1299</div>
          <div><strong style={{fontSize:'16px'}}>₹393</strong> <span className="estimate-discount">(70% OFF)</span></div>
        </div>
      </div>

      <div className="seller-row">
        <span className="seller-label">Seller:</span> <strong>KARTBIN ONLINE SERVIC...</strong> <ChevronRight size={16} />
      </div>

      <div className="service-row">
        <div className="service-icon-wrap">
          <CreditCard size={24} />
          <CheckCircle2 size={12} fill="#03a685" color="white" className="service-check" />
        </div>
        <div className="service-info">
          <div className="service-title">Pay on Delivery is available</div>
          <div className="service-subtext">₹10 additional fee applicable</div>
        </div>
      </div>

      <div className="service-row">
        <div className="service-icon-wrap">
          <RefreshCw size={24} />
          <CheckCircle2 size={12} fill="#03a685" color="white" className="service-check" />
        </div>
        <div className="service-info">
          <div className="service-title">Hassle free 7 days Return & Exchange</div>
        </div>
      </div>
    </div>
  );
}
