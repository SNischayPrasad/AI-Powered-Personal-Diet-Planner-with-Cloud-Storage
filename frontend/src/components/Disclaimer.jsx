import Icon from "./Icon.jsx";

export const DEFAULT_DISCLAIMER =
  "Plans are educational, general-wellness examples produced by a demo application. They are " +
  "not medical or clinical nutrition advice. Talk to a qualified healthcare professional or " +
  "registered dietitian before changing your diet.";

export default function Disclaimer({ text = DEFAULT_DISCLAIMER }) {
  return (
    <aside className="disclaimer" aria-label="Disclaimer">
      <Icon name="info" size={18} />
      <p>{text}</p>
    </aside>
  );
}
