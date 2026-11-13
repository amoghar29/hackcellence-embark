// Loads the Google Maps JavaScript API once, in English. Rejects when there is no key, the script cannot
// load, or Google refuses the key (gm_authFailure), so the caller can fall back to OpenStreetMap.
export const GOOGLE_KEY = import.meta.env?.GOOGLE_MAP_API || ''

let loading = null

export function loadGoogleMaps(key = GOOGLE_KEY) {
  if (!key) return Promise.reject(new Error('no Google Maps key'))
  if (window.google?.maps?.Map) return Promise.resolve(window.google.maps)
  loading ||= new Promise((resolve, reject) => {
    window.__embarkMapsReady = () => resolve(window.google.maps)
    // Google calls this when it refuses the key, possibly after the map has started drawing
    window.gm_authFailure = () => { reject(new Error('Google refused the Maps key')); window.dispatchEvent(new Event('gmaps-failed')) }
    const s = document.createElement('script')
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&language=en&callback=__embarkMapsReady&loading=async`
    s.async = true
    s.onerror = () => { loading = null; reject(new Error('Google Maps did not load')) }
    document.head.appendChild(s)
  })
  return loading
}
