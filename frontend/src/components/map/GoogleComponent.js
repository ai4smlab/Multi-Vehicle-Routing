import { GoogleMap, LoadScript, Marker } from '@react-google-maps/api';

const containerStyle = {
  width: '100%',
  height: '400px',
};

const center = {
  lat: 24.7136, 
  lng: 46.6753, 
};

const Google_API_KEY = process.env.NEXT_PUBLIC_Google_API_KEY;

const GoogleComponent = () => {
  return (
    <LoadScript Google_API_KEY>
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={center}
        zoom={10}
      >
        {/* Add a marker */}
        <Marker position={center} />
      </GoogleMap>
    </LoadScript>
  );
};

export default GoogleComponent;