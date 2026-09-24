import Icon from "./Icon.jsx";

export default function EmptyState({ icon = "info", title, children, action }) {
  return (
    <div className="empty">
      <span className="empty__icon">
        <Icon name={icon} size={26} />
      </span>
      <p className="empty__title">{title}</p>
      {children && <p className="empty__body">{children}</p>}
      {action && <div className="empty__action">{action}</div>}
    </div>
  );
}
