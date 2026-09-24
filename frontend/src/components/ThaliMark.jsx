// The brand mark: a steel plate seen from above with four bowls, one per meal.
export default function ThaliMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle cx="16" cy="16" r="15" fill="#DDE3E5" stroke="#1F3B2D" strokeWidth="1.6" />
      <circle cx="16" cy="16" r="11.5" fill="none" stroke="#A7B2B6" strokeWidth="0.8" />
      <circle cx="10.5" cy="10.5" r="4.1" fill="#A85A27" />
      <circle cx="21.5" cy="10.5" r="4.8" fill="#A85A27" />
      <circle cx="21.5" cy="21.5" r="3.1" fill="#A85A27" />
      <circle cx="10.5" cy="21.5" r="4.4" fill="#A85A27" />
    </svg>
  );
}
