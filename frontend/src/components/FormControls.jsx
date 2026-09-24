// Accessible form building blocks: every control has a visible label, hints and errors are
// linked with aria-describedby, and invalid fields are announced with aria-invalid.

export function Field({ id, label, hint, error, children }) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ");
  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy || undefined, "aria-invalid": Boolean(error) })}
      {hint && (
        <p className="field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field__error" id={`${id}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}

// A radio group shown as cards (dietary preference, goal).
export function ChoiceCards({ name, legend, options, value, onChange, error }) {
  return (
    <fieldset className={`choices${error ? " field--invalid" : ""}`}>
      <legend className="field__label">{legend}</legend>
      <div className="choices__grid">
        {options.map((option) => (
          <label key={option.value} className={`choice${value === option.value ? " is-selected" : ""}`}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="choice__label">{option.label}</span>
            {option.hint && <span className="choice__hint">{option.hint}</span>}
          </label>
        ))}
      </div>
      {error && <p className="field__error">{error}</p>}
    </fieldset>
  );
}

// A checkbox group shown as toggle chips (allergies).
export function ChipGroup({ legend, hint, options, values, onChange }) {
  const toggle = (value) =>
    onChange(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  return (
    <fieldset className="chips">
      <legend className="field__label">{legend}</legend>
      {hint && <p className="field__hint">{hint}</p>}
      <div className="chips__list">
        {options.map((option) => (
          <label key={option.value} className={`chip${values.includes(option.value) ? " is-selected" : ""}`}>
            <input
              type="checkbox"
              value={option.value}
              checked={values.includes(option.value)}
              onChange={() => toggle(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
