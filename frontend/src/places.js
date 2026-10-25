// AEP stores street and city in capitals ("POLLARD", "VINTON"). We only ever show the
// street name and town, never a house number.

function titleCase(text) {
  return text.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
}

// "Pollard, Vinton", or null when the home has no street on record.
export function placeName(home) {
  if (!home?.street) return null
  return home.city ? `${titleCase(home.street)}, ${titleCase(home.city)}` : titleCase(home.street)
}
