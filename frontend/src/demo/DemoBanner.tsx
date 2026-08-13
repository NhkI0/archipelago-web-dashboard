import { IS_DEMO } from "../api";
import { useT } from "../i18n";

export default function DemoBanner() {
  const { t } = useT();
  if (!IS_DEMO) return null;
  return (
    <div className="bg-brand-orange px-4 py-1.5 text-center text-caption-up uppercase tracking-wider text-white">
      {t("demo.banner")}
    </div>
  );
}
