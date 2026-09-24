export function Loader({ label = "Loading" }) {
  return (
    <span className="loader" role="status">
      <span className="loader__dot" />
      <span className="loader__dot" />
      <span className="loader__dot" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function PageLoader({ label = "Loading" }) {
  return (
    <div className="page-loader">
      <Loader label={label} />
    </div>
  );
}
