export function Stars({ rating, reviews }: { rating: number; reviews: number }) {
  const full = Math.round(rating);
  return (
    <span className="stars" aria-label={`${rating} out of 5 from ${reviews} reviews`}>
      {"★".repeat(full)}
      {"☆".repeat(5 - full)}
      <small>
        {rating} ({reviews})
      </small>
    </span>
  );
}
