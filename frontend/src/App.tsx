import { Route, Routes } from "react-router-dom";
import HintNotifier from "./components/HintNotifier";
import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard";
import SlotDetail from "./pages/SlotDetail";
import Hints from "./pages/Hints";
import HallOfFame from "./pages/HallOfFame";
import Login from "./pages/Login";
import { LanguageProvider, useT } from "./i18n";
import { ThemeProvider } from "./theme";
import { ConfigProvider, useConfig } from "./config";
import { MAINTAINER_LINKS, SocialLinks } from "./components/SocialLinks";
import DemoBanner from "./demo/DemoBanner";

function Footer() {
  const { t } = useT();
  const config = useConfig();
  return (
    <footer className="border-t hair bg-canvas px-4 sm:px-12 py-8 sm:py-12 text-body text-body-sm transition-colors duration-300">
      <div className="mx-auto max-w-[1200px] flex flex-col gap-6">
        <div className="flex flex-col sm:flex-row sm:justify-between gap-2 text-center sm:text-left">
          <span className="text-steel">{config.footer.left || t("footer.left")}</span>
          <span className="text-steel">{config.footer.right || t("footer.right")}</span>
        </div>
        {/* Maintainer links: the only socials shown, baked in, not configurable */}
        <div className="flex items-center gap-3 text-steel">
          <span className="text-caption-up uppercase tracking-wider">{t("footer.report")}</span>
          <SocialLinks links={MAINTAINER_LINKS} />
        </div>
      </div>
    </footer>
  );
}

function Shell() {
  const config = useConfig();
  return (
    <div className="min-h-full flex flex-col bg-canvas transition-colors duration-300">
      <DemoBanner />
      <TopNav />
      <HintNotifier />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/slot/:name" element={<SlotDetail />} />
          <Route path="/hints" element={<Hints />} />
          {config.features.hall_of_fame && <Route path="/hall-of-fame" element={<HallOfFame />} />}
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <LanguageProvider>
    <ConfigProvider>
      <Shell />
    </ConfigProvider>
    </LanguageProvider>
    </ThemeProvider>
  );
}
