import React from 'react';
import { MapPin, ChevronDown } from 'lucide-react';

export default function LocationBar() {
  return (
    <div className="location-bar-wrapper">
      <div className="location-bar">
        <MapPin size={22} className="location-icon" />
        <div className="location-text">
          <span className="location-bold">Zuari Nagar - </span>
          <span className="location-regular">South Goa, Vasco Da Gama, 403726, Goa</span>
        </div>
        <ChevronDown size={24} className="chevron-icon" />
      </div>
    </div>
  );
}
