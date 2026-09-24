import Icon from "./Icon.jsx";

const ICONS = { info: "info", success: "check", error: "alert", warning: "alert" };

export default function Alert({ tone = "info", title, children, action }) {
  return (
    <div className={`alert alert--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name={ICONS[tone]} className="alert__icon" />
      <div className="alert__content">
        {title && <p className="alert__title">{title}</p>}
        {children && <div className="alert__body">{children}</div>}
      </div>
      {action && <div className="alert__action">{action}</div>}
    </div>
  );
}
