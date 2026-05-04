import { Route, Routes } from "react-router-dom";
import HintNotifier from "./components/HintNotifier";
import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard";
import SlotDetail from "./pages/SlotDetail";
import Hints from "./pages/Hints";
import Login from "./pages/Login";
import { LanguageProvider, useT } from "./i18n";
import { ThemeProvider } from "./theme";

function Footer() {
  const { t } = useT();
  return (
    <footer className="border-t hair bg-canvas px-12 py-12 text-body text-body-sm transition-colors duration-300">
      <div className="mx-auto max-w-[1200px] flex justify-between">
        <span className="text-steel">{t("footer.left")}</span>
        <span className="text-steel">{t("footer.right")}</span>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <LanguageProvider>
      <div className="min-h-full flex flex-col bg-canvas transition-colors duration-300">
        <TopNav />
        <HintNotifier />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/slot/:name" element={<SlotDetail />} />
            <Route path="/hints" element={<Hints />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </LanguageProvider>
    </ThemeProvider>
  );
}
