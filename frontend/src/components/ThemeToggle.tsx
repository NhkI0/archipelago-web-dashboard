import { useTheme } from "../theme";
import { useT } from "../i18n";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const { t } = useT();
  const isDay = theme === "light";
  return (
    <button
      type="button"
      onClick={toggle}
      role="switch"
      aria-checked={isDay}
      aria-label={t("common.theme.toggle_aria")}
      title={t("common.theme.toggle_aria")}
      className={`ms-toggle ${isDay ? "day" : ""}`}
    >
      <span className={`ms-orb ${isDay ? "sun" : ""}`} />
    </button>
  );
}
