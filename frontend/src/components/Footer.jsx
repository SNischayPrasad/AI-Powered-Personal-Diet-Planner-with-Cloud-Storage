const REPOSITORY_URL = "https://github.com/SNischayPrasad/AI-Powered-Personal-Diet-Planner-with-Cloud-Storage";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <p>
          Educational demo. Plans are general-wellness examples, not medical advice. Use synthetic
          data only.
        </p>
        <p className="footer__meta">
          Cloud computing project · FastAPI · React · PostgreSQL · S3-compatible storage ·{" "}
          <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
            Source on GitHub
          </a>
        </p>
      </div>
    </footer>
  );
}
