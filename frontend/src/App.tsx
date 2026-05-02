import { Route, Routes } from "react-router-dom";
import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard";
import SlotDetail from "./pages/SlotDetail";
import Hints from "./pages/Hints";
import Login from "./pages/Login";

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <TopNav />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/slot/:name" element={<SlotDetail />} />
          <Route path="/hints" element={<Hints />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
      <footer className="border-t hair bg-canvas px-12 py-12 text-body text-body-sm">
        <div className="mx-auto max-w-[1200px] flex justify-between">
          <span className="font-mono text-mutedSoft">archipelago · nguengant.fr</span>
          <span className="text-mutedSoft">self-hosted multiworld</span>
        </div>
      </footer>
    </div>
  );
}
